# GKE Security and Network Policy Configuration
# Reference existing cluster via data source, apply additional configs

terraform {
  required_version = ">= 1.5.0"
}

data "google_container_cluster" "payment_cluster" {
  name     = "payment-engine-${var.environment}"
  location = var.region
}

# ============================================================================
# ADDITIONAL NODE POOLS
# ============================================================================

resource "google_container_node_pool" "payment_worker" {
  name       = "payment-worker"
  location   = var.region
  cluster    = data.google_container_cluster.payment_cluster.id

  node_config {
    machine_type    = "n2-standard-8"
    spot            = var.environment != "prod"
    service_account = google_service_account.payment_engine.email
    workload_metadata_config { mode = "GKE_METADATA" }
    disk_type    = "pd-ssd"
    disk_size_gb = 100
  }

  node_count = 3

  management {
    auto_upgrade = true
    auto_repair  = true
  }

  autoscaling {
    min_node_count = 3
    max_node_count = 20
  }
}

resource "google_container_node_pool" "message_broker" {
  name       = "message-broker"
  location   = var.region
  cluster    = data.google_container_cluster.payment_cluster.id

  node_config {
    machine_type    = "n2-standard-16"
    spot            = false
    service_account = google_service_account.payment_engine.email
    workload_metadata_config { mode = "GKE_METADATA" }
    disk_type    = "pd-ssd"
    disk_size_gb = 200
  }

  node_count = 2

  management {
    auto_upgrade = true
    auto_repair  = true
  }

  autoscaling {
    min_node_count = 2
    max_node_count = 10
  }
}

resource "google_container_node_pool" "db_proxy" {
  name       = "db-proxy"
  location   = var.region
  cluster    = data.google_container_cluster.payment_cluster.id

  node_config {
    machine_type    = "n2-standard-4"
    spot            = false
    service_account = google_service_account.payment_engine.email
    workload_metadata_config { mode = "GKE_METADATA" }
  }

  node_count = 2

  management {
    auto_upgrade = true
    auto_repair  = true
  }
}

resource "google_container_node_pool" "hsm_gateway_eks" {
  name = "hsm-gateway-eks"
  location   = var.region
  cluster    = data.google_container_cluster.payment_cluster.id

  node_config {
    machine_type       = "n2-standard-4"
    spot               = false
    service_account    = google_service_account.payment_engine.email
    local_ssd_count    = 1
    disk_type          = "local-ssd"
    workload_metadata_config { mode = "GKE_METADATA" }
  }

  node_count = 1

  management {
    auto_upgrade = true
    auto_repair  = true
  }
}

# ============================================================================
# NETWORK POLICIES (Calico)
# ============================================================================

resource "google_project_iam_member" "network_policy_binding" {
  project = var.project_id
  role    = "roles/compute.networkAdmin"
  member  = "serviceAccount:${google_service_account.payment_engine.email}"
}

# ============================================================================
# BINARY AUTHORIZATION
# ============================================================================

resource "google_binary_authorization_policy" "payment_binauthz" {
  global_policy_evaluation_mode = "ENABLE"

  default_admission_rule {
    enforcement_mode  = "ENFORCED_BLOCK_AND_AUDIT_LOG"
    evaluation_mode   = "REQUIRE_ATTESTATION"
    require_attestors = [google_binary_authorization_attestor.payment_attestor.name]
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/distroless/*"
  }
}

resource "google_binary_authorization_attestor" "payment_attestor" {
  name        = "payment-attestor-${var.environment}"
  description = "Attestor for payment switch container images"

  attestor_note {
    note_reference = google_endpoints_service.payment_binauthz.note_id
    public_keys {
      id       = "k8s-migrator.gitconnect.gcr.io"
      pkix_pem = file("${path.module}/keys/attestor_pkix.pem")
    }
  }
}

resource "google_endpoints_service" "payment_binauthz" {
  name     = "payment-binauthz-attestor-${var.environment}"
  project  = var.project_id

  config {
    protobuf_descriptor = file("${path.module}/protos/binauthz.pb")
    services            = [google_endpoints_service.payment_binauthz.name]
  }

  depends_on = [google_project_service.binauthz_api]
}

resource "google_project_service" "binauthz_api" {
  service  = "binaryauthorization.googleapis.com"
  disable_dependent_services = true
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "cluster_id" {
  value = data.google_container_cluster.payment_cluster.id
}

output "cluster_master_version" {
  value = data.google_container_cluster.payment_cluster.master_version
}

output "node_pool_ids" {
  value = {
    payment_worker = google_container_node_pool.payment_worker.id
    message_broker = google_container_node_pool.message_broker.id
    db_proxy       = google_container_node_pool.db_proxy.id
    hsm_gateway    = google_container_node_pool.hsm_gateway.id
  }
}