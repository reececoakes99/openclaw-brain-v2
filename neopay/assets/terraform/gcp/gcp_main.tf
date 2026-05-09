terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "neopay-terraform-state"
    prefix = "protocol-engineering/gcp"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}





# ============================================================================
# NETWORK
# ============================================================================

resource "google_compute_network" "payment_vpc" {
  name                    = "payment-vpc-${var.environment}"
  auto_create_subnetworks = false
  description             = "Payment switch VPC network"
}

resource "google_compute_subnetwork" "public" {
  name          = "payment-public-${var.environment}"
  network       = google_compute_network.payment_vpc.id
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  description   = "Public subnet for load balancers and NAT"

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata            = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "private" {
  name          = "payment-private-${var.environment}"
  network       = google_compute_network.payment_vpc.id
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  description   = "Private subnet for application workloads"
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata            = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "management" {
  name          = "payment-mgmt-${var.environment}"
  network       = google_compute_network.payment_vpc.id
  ip_cidr_range = "10.0.2.0/24"
  region        = var.region
  description   = "Management subnet for bastion/Jump Host"
}

resource "google_compute_subnetwork" "hsm" {
  name          = "payment-hsm-${var.environment}"
  network       = google_compute_network.payment_vpc.id
  ip_cidr_range = "10.0.3.0/24"
  region        = var.region
  description   = "Isolated subnet for HSM/PoC devices"
  private_ip_google_access = true
}

# Cloud NAT for egress from private subnets
resource "google_compute_router" "nat_router" {
  name    = "payment-nat-${var.environment}"
  network = google_compute_network.payment_vpc.id
  region  = var.region
}

resource "google_compute_router_nat" "nat" {
  name                               = "payment-nat-${var.environment}"
  router                             = google_compute_router.nat_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  min_ports_per_vm                  = 64
  max_ports_per_vm                  = 65536
}

# ============================================================================
# GKE CLUSTER
# ============================================================================

resource "google_container_cluster" "payment_cluster" {
  name                     = "payment-engine-${var.environment}"
  location                 = var.region
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.payment_vpc.name
  subnetwork = google_compute_subnetwork.private.name

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  networking_mode = "VPC_NATIVE"

  node_locations = ["europe-west1-b", "europe-west1-c", "europe-west1-d"]

  addons_config {
    horizontal_pod_autoscaling { disabled = false }
    http_load_balancing        { disabled = false }
    gcpfilestore_csi_driver    { disabled = true }
    config_connector           { disabled = false }
    dns_cache_config           { disabled = false }
  }

  maintenance_policy {
    recurring_schedule {
      day          = "DAY_UNSPECIFIED"
      start_time   = "04:00"
      duration     = "03h00m"
      frequency    = "FREQ_WEEKLY"
    }
    maintenance_exclusions {
    }
  }

  monitoring_config {
    advanced_datapath_observability_config {
      enable_metrics = true
    }
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  release_channel {
    channel = "REGULAR"
  }

  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }

  logging_config {
    variant = "VARIANT_DEFAULT"
  }

  dynamic "node_pool" {
    for_each = {
      "payment-engine" = { version = "1.29", machine = "n2-highmem-8", min = 3, max = 20 }
      "scheme-interface" = { version = "1.29", machine = "n2-standard-16", min = 2, max = 10 }
    }
    content {
      name = node_pool.key
      node_config {
        machine_type    = node_pool.value.machine
        service_account = google_service_account.gke_nodes.email
        spot            = var.environment != "prod"
        workload_metadata_config { mode = "GKE_METADATA" }
        boot_disk_kms_key = ""
      }
      node_count = node_pool.value.min
      management {
        auto_upgrade = true
        auto_repair  = true
      }
      upgrade_settings {
        strategy       = "SURGE"
        max_surge      = 1
        max_unavailable = 0
      }
    }
  }
}

# HSM gateway node pool — isolated, local SSD
resource "google_container_node_pool" "hsm_gateway" {
  name       = "hsm-gateway"
  location   = var.region
  cluster    = google_container_cluster.payment_cluster.name

  node_config {
    machine_type  = "n2-standard-4"
    spot          = false
    service_account = google_service_account.gke_nodes.email
    local_ssd_count = 1

    disk_type = "local-ssd"
    workload_metadata_config { mode = "GKE_METADATA" }
  }

  node_count = 1

  management {
    auto_upgrade = true
    auto_repair  = true
  }
}

# ============================================================================
# CLOUD SQL (PostgreSQL)
# ============================================================================

resource "google_compute_global_address" "sql_private_ip" {
  name          = "payment-sql-private-${var.environment}"
  purpose       = "VPC_PEERING"
  prefix_length = 16
  network       = google_compute_network.payment_vpc.id
}

resource "google_service_networking_connection" "sql_vpc_peering" {
  service       = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql_private_ip.name]
  network       = google_compute_network.payment_vpc.id
}

resource "google_sql_database_instance" "payment_db" {
  name             = "payment-db-${var.environment}"
  database_version = "POSTGRES_16"
  region           = var.region

  deletion_protection = var.environment == "prod"

  settings {
    tier              = "db-n1-standard-4"
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 500
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled        = false
      private_network      = google_compute_network.payment_vpc.id
      require_ssl          = true
      ssl_mode             = "ENFORCED"
      allocated_ip_range   = null
      # Use VPC peering via google_service_networking_connection
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = var.environment == "prod"
      backup_retention_settings {
        retained_backups = 30
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    database_flags {
      name  = "log_statement"
      value = "ddl"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "pgaudit.log"
      value = "read,write"
    }

    effective_labels = {
      environment = var.environment
      component   = "database"
    }
  }
}

resource "google_sql_user" "payment_app" {
  name     = "payment_app"
  instance = google_sql_database_instance.payment_db.name
  password = google_secret_manager_secret.db_password.secret_data
}

# ============================================================================
# REDIS ENTERPRISE
# ============================================================================

resource "google_redis_instance" "payment_redis" {
  name           = "payment-redis-${var.environment}"
  tier           = "ENTERPRISE"
  memory_size_gb = 6
  region         = var.region

  authorized_network = google_compute_network.payment_vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  redis_version     = "REDIS_7_0"

  replica_count         = 2
  read_replica_mode    = "READ_REPLICAS_ENABLED"
  read_endpoint        = true
  read_endpoint_role   = "READ_REPLICA"

  persistence_config {
    rdb_next_snapshot_time = "07:00"
    rdb_snapshot_period    = "6_HOURS"
  }

  transit_encryption_mode = "SERVER_AUTHENTICATION"
  auth_string_enabled     = true

  effective_labels = {
    environment = var.environment
    component   = "cache"
  }
}

# ============================================================================
# CLOUD ARMOR (WAF)
# ============================================================================

resource "google_compute_security_policy" "payment_waf" {
  name        = "payment-waf-${var.environment}"
  description = "Cloud Armor security policy for payment switch"

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
      rule_visibility = "STANDARD"
    }
  }

  # Preconfigured ruleset: OWASP ModSecurity WAF
  # Note: attach to backend services after creation

  rule {
    action   = "allow"
    priority = 2147483647
    description = "Default rule — allow all"
  }
}

# ============================================================================
# SECRET MANAGER
# ============================================================================

resource "google_secret_manager_secret" "db_password" {
  secret_id = "payment-db-password-${var.environment}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "hsm_api_key" {
  secret_id = "payment-hsm-api-key-${var.environment}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "redis_password" {
  secret_id = "payment-redis-password-${var.environment}"
  replication {
    auto {}
  }
}

# ============================================================================
# CLOUD MONITORING
# ============================================================================

resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "Payment Switch — Error Rate > 1%"
  conditions {
    display_name = "Error rate"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"payment-engine-${var.environment}\" AND metric.type=\"kubernetes.io/container/restart_count\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
      }
    }
  }
  notification_channels = []
  alert_strategy {
    auto_close = "1800s"
  }
}

# ============================================================================
# FILESTORE (shared config)
# ============================================================================

resource "google_filestore_instance" "shared_config" {
  name        = "payment-config-${var.environment}"
  location    = var.region
  tier        = "ENTERPRISE"
  file_shares {
    capacity_gb = 1024
    name        = "shared"
  }
  networks {
    network      = google_compute_network.payment_vpc.name
    modes        = ["PRIVATE_VPC"]
    reserved_ip_range = "10.0.4.0/29"
  }
}

# ============================================================================
# ARTIFACT REGISTRY
# ============================================================================

resource "google_artifact_registry_repository" "payment_images" {
  location      = var.region
  repository_id = "payment-images-${var.environment}"
  description   = "Container images for payment switch"
  format        = "DOCKER"
  encryption_key = google_kms_crypto_key.artifacts_key.id
}

# ============================================================================
# KMS (for artifact encryption)
# ============================================================================

resource "google_kms_key_ring" "payment_keyring" {
  name     = "payment-keyring-${var.environment}"
  location = "global"
}

resource "google_kms_crypto_key" "artifacts_key" {
  name            = "payment-artifacts-key-${var.environment}"
  key_ring        = google_kms_key_ring.payment_keyring.id
  key_purpose     = "ASYMMETRIC_SIGN"
  version_template {
    algorithm = "RSA_SIGN_PSS_2048_SHA256"
  }
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

resource "google_service_account" "gke_nodes" {
  account_id   = "payment-gke-nodes-${var.environment}"
  display_name = "Payment Switch GKE Nodes"
}

resource "google_service_account" "payment_engine" {
  account_id   = "payment-engine-sa-${var.environment}"
  display_name = "Payment Switch Engine"
}

resource "google_project_iam_member" "gke_node_sa_binding" {
  project = var.project_id
  role    = "roles/container.nodeServiceAccount"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "engine_sa_binding" {
  for_each = toset([
    "roles/container.developer",
    "roles/cloudsql.client",
    "roles/redis.editor",
    "roles/secretmanager.secretAccessor",
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.payment_engine.email}"
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "cluster_name" {
  value = google_container_cluster.payment_cluster.name
}

output "cluster_endpoint" {
  value     = google_container_cluster.payment_cluster.endpoint
  sensitive = true
}

output "sql_instance_connection_name" {
  value = google_sql_database_instance.payment_db.connection_name
}

output "redis_host" {
  value = google_redis_instance.payment_redis.host
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.payment_images.repository_id}"
}