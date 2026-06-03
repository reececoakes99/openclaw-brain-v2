# GCP Security Hardening — VPC Service Controls, KMS, Cloud Armor, SIEM
# Reference module for security configurations (works with gcp_main.tf)

# ============================================================================
# VPC SERVICE CONTROLS
# ============================================================================

resource "google_access_context_manager_service_perimeter" "payment_perimeter" {
  parent = "projects/${var.project_id}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.payment_policy.id}/servicePerimeters/payment-prod"
  title  = "Payment Switch Service Perimeter"

  status {
    resources = [
      "projects/${var.project_id}",
    ]

    ingress_policies {
      ingress_from {
        sources {
          resource_filters {
            resource = "projects/${var.project_id}"
          }
        }
        identities = ["serviceAccount:${google_service_account.payment_engine.email}"]
        ingress_source = google_access_context_manager_service_perimeter.payment_perimeter.status.ingress_policies[*]
      }
      ingress_to {
        resources = ["projects/${var.project_id}"]
        operations {
          services = ["bigquery.googleapis.com", "storage.googleapis.com", "sqladmin.googleapis.com", "redis.googleapis.com"]
          restrictions {
            principal = ["serviceAccount:${google_service_account.payment_engine.email}"]
          }
        }
      }
    }

    egress_policies {
      egress_from {
        identities = ["serviceAccount:${google_service_account.payment_engine.email}"]
      }
      egress_to {
        resources = []
        operations {
          services = ["storage.googleapis.com"]
          restrictions {
            resources = ["projects/${var.project_id}/buckets/payment-clearing-*"]
          }
        }
      }
    }
  }

  spec {
    resources = ["projects/${var.project_id}"]
  }
}

resource "google_access_context_manager_access_policy" "payment_policy" {
  title = "Payment Switch Access Policy"
}

# ============================================================================
# CLOUD KMS — Key Management
# ============================================================================

resource "google_kms_key_ring" "payment_hsm_keyring" {
  name     = "payment-hsm-keyring"
  location = "global"
}

resource "google_kms_crypto_key" "lmk_master_key" {
  name            = "lmk-master-key"
  key_ring        = google_kms_key_ring.payment_hsm_keyring.id
  key_purpose     = "ENCRYPT_DECRYPT"
  skip_initial_version_creation = true

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "HSM"
  }

  rotation_policy {
    rotation_period = "7776000s"  # 90 days
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "zmk_key" {
  name            = "zmk-zone-master-key"
  key_ring        = google_kms_key_ring.payment_hsm_keyring.id
  key_purpose     = "ENCRYPT_DECRYPT"
  skip_initial_version_creation = true

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "HSM"
  }

  rotation_policy {
    rotation_period = "2592000s"  # 30 days
  }
}

resource "google_kms_crypto_key" "mac_key" {
  name            = "mac-working-key"
  key_ring        = google_kms_key_ring.payment_hsm_keyring.id
  key_purpose     = "ENCRYPT_DECRYPT"
  skip_initial_version_creation = true

  version_template {
    algorithm = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "HSM"
  }
}

# ============================================================================
# CERTIFICATE AUTHORITY SERVICE
# ============================================================================

resource "google_certificate_authority_service_certificate_authority" "payment_ca" {
  location     = var.region
  certificate_authority_id = "payment-root-ca-${var.environment}"
  config {
    x509_config {
      ca_options {
        is_ca = true
        max_path_length = 0
      }
      key_usage {
        base_key_usage {
          digital_signature = true
          key_cert_sign = true
          crl_sign = true
        }
        extended_key_usage {
          server_auth = false
          client_auth = false
        }
      }
      subject_config {
        subject = {
          common_name = "payment-root-ca.${var.environment}.internal"
          organization = "Payment Switch"
        }
      }
      v3_extensions {
        key_usage {
          base_key_usage {
            critical = true
          }
        }
      }
    }
    subject_mode = "CODIFIED"
  }
  certificate_authority_type = "SELF_SIGNED"
  key_spec {
    cloud_kms_key_version = google_kms_crypto_key.lmk_master_key.id
  }
  lifespan = "87600h"  # 10 years
}

# ============================================================================
# CLOUD ARMOR ADVANCED RULES
# ============================================================================

resource "google_compute_security_policy" "payment_waf_advanced" {
  name        = "payment-waf-advanced-${var.environment}"
  description = "Advanced WAF rules for payment switch"

  # Rate limiting
  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable            = true
      rule_visibility   = "STANDARD"
    }
  }

  # SQL injection protection
  rule {
    action      = "deny(403)"
    priority    = 1000
    description  = "Block SQL injection attempts"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }
  }

  # XSS protection
  rule {
    action      = "deny(403)"
    priority    = 1001
    description  = "Block XSS attempts"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
  }

  # Protocol attack protection
  rule {
    action      = "deny(403)"
    priority    = 1002
    description  = "Block protocol attacks"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('protocolattack-v33-stable')"
      }
    }
  }

  # RATE_LIMIT: max 100 req/s per IP for payment endpoint
  rule {
    action      = "throttle"
    priority    = 900
    description  = "Rate limit payment API"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
        versioned_expr = "SRC_IPS_V1"
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      rate_limit_threshold {
        count        = 100
        interval_sec = 1
      }
      ban_duration_sec = 60
    }
  }

  # Allow trusted IPs (scheme endpoints)
  rule {
    action      = "allow"
    priority    = 100
    description  = "Allow scheme connectivity"
    match {
      expr {
        expression = "origin.region_code in ['GB', 'DE', 'US', 'IE']"
      }
    }
  }

  # Default deny
  rule {
    action      = "deny(403)"
    priority    = 2147483647
    description  = "Default deny"
  }
}

# ============================================================================
# SECURITY HEALTH ANALYTICS
# ============================================================================

resource "google_project_service" "security_health_analytics" {
  service = "securityhealthanalytics.googleapis.com"
}

resource "google_security_center_config" "payment_scc" {
  security_center_config_name = "organizations/${var.project_id}/configs/default"
  enable_assets = true

  finding_publish_config {
    enable = true
  }

  security_marks_config {
    restrict_assets_by_tag = false
  }
}

# ============================================================================
# FORSETI CONFIG VALIDATOR
# ============================================================================

# Cloud Armor association (attach WAF to load balancer)
resource "google_compute_backend_service" "payment_api_backend" {
  name        = "payment-api-backend-${var.environment}"
  protocol    = "HTTPS"
  ssl         = true

  backend {
    group = google_compute_instance_group.payment_api.instance_group
  }

  security_policy = google_compute_security_policy.payment_waf_advanced.id

  health_checks = google_compute_health_check.payment_api_hc.id

  log_config {
    enable = true
    sample_rate = 0.5
  }
}

resource "google_compute_health_check" "payment_api_hc" {
  name               = "payment-api-hc-${var.environment}"
  healthy_threshold   = 2
  unhealthy_threshold = 3
  timeout_sec         = 5

  https_health_check {
    port         = 8443
    request_path = "/health"
  }
}

resource "google_compute_instance_group" "payment_api" {
  name        = "payment-api-ig-${var.environment}"
  zone        = "${var.region}-b"
  instances   = []
  named_port {
    name = "https"
    port = 8443
  }
}

# ============================================================================
# PRIVATE GOOGLE ACCESS
# ============================================================================

resource "google_compute_subnetwork" "public_security" {
  name = "payment-public-${var.environment}"
  private_ip_google_access = true  # Already set in gcp_main.tf, confirmation
}

# Egress firewall rules (deny-all default)
resource "google_compute_firewall" "egress_deny_all" {
  name          = "egress-deny-all-${var.environment}"
  network       = google_compute_network.payment_vpc.name
  direction     = "EGRESS"
  priority      = 65534
  destination_ranges = ["0.0.0.0/0"]
  action        = "deny"

  # Allow DNS, NTP, GCP APIs
  allow {
    protocol = "udp"
    ports    = ["53"]
  }
  allow {
    protocol = "tcp"
    ports    = ["53", "123", "443", "80"]
  }
}

resource "google_compute_firewall" "allow_internal" {
  name        = "allow-internal-${var.environment}"
  network     = google_compute_network.payment_vpc.name
  direction   = "INGRESS"
  priority    = 65534
  source_ranges = ["10.0.0.0/8"]
  action      = "allow"
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "kms_keyring" {
  value = google_kms_key_ring.payment_hsm_keyring.id
}

output "ca_resource" {
  value = google_certificate_authority_service_certificate_authority.payment_ca.id
}

output "waf_policy" {
  value = google_compute_security_policy.payment_waf_advanced.id
}