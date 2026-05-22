# GCP Infrastructure for Paybox Payment Gateway
# terraform 1.5+ | google provider 5.x

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "vpcaccess.googleapis.com"
  ])
  project = var.project_id
  service = each.value
  disable_dependent_services = true
}

# VPC Network
resource "google_compute_network" "paybox_vpc" {
  name                    = "paybox-vpc-${var.environment}"
  auto_create_subnetworks = false
  description             = "Paybox payment gateway VPC"
}

# Subnets
resource "google_compute_subnetwork" "paybox_api" {
  name          = "paybox-api-${var.environment}"
  network       = google_compute_network.paybox_vpc.id
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  private_ip_google_access = true

  log_config {
    aggregation_interval = "10s"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "paybox_worker" {
  name          = "paybox-worker-${var.environment}"
  network       = google_compute_network.paybox_vpc.id
  ip_cidr_range = "10.0.2.0/24"
  region        = var.region
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "paybox_db" {
  name          = "paybox-db-${var.environment}"
  network       = google_compute_network.paybox_vpc.id
  ip_cidr_range = "10.0.3.0/28"
  region        = var.region
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "paybox_hsm" {
  name          = "paybox-hsm-${var.environment}"
  network       = google_compute_network.paybox_vpc.id
  ip_cidr_range = "10.0.4.0/28"
  region        = var.region
  private_ip_google_access = true
}

# Cloud SQL PostgreSQL
resource "google_sql_database_instance" "paybox_db" {
  name             = "paybox-db-${var.environment}"
  region           = var.region
  database_version = "POSTGRES_15"
  deletion_protection = true

  settings {
    tier              = "db-n1-standard-4"
    availability_type = "REGIONAL"
    disk_size         = 500
    disk_type         = "PD_SSD"
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.paybox_vpc.id
      require_ssl     = true
    }
    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
    }
  }
}

resource "google_sql_database" "paybox" {
  name     = "paybox"
  instance = google_sql_database_instance.paybox_db.name
}

resource "google_sql_user" "paybox_app" {
  name     = "paybox_app"
  instance = google_sql_database_instance.paybox_db.name
  password = random_password.db_password.result
}

# Redis Memorystore
resource "google_redis_instance" "paybox_redis" {
  name           = "paybox-redis-${var.environment}"
  region         = var.region
  tier           = "STANDARD_HA"
  memory_size_gb = 3
  version        = "REDIS_7_0"

  authorized_network = google_compute_network.paybox_vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  redis_config {
    maxmemory_policy = "allkeys-lru"
    pubsub_flow_control = true
  }
}

# GKE Cluster (Autopilot)
resource "google_container_cluster" "paybox_gke" {
  name                     = "paybox-gke-${var.environment}"
  location                 = var.region
  release_channel          = "regular"
  enable_autopilot         = true

  network    = google_compute_network.paybox_vpc.id
  subnetwork = google_compute_subnetwork.paybox_api.name

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block   = "172.16.0.0/28"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  node_config {
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

# Cloud Armor (WAF)
resource "google_compute_security_policy" "paybox_waf" {
  name        = "paybox-waf-${var.environment}"
  description  = "Paybox WAF security policy"

  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }
  }

  rule {
    action   = "deny(403)"
    priority = 1001
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
  }

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

# Serverless VPC Access (for Cloud Run/Cloud Functions)
resource "google_vpc_access_connector" "paybox_vpc_conn" {
  name          = "paybox-vpc-connector"
  region        = var.region
  network       = google_compute_network.paybox_vpc.name
  min_instances = 2
  max_instances = 10
  machine_type  = "e2-standard"
}

# Secret Manager
resource "google_secret_manager_secret" "api_key" {
  secret_id = "paybox-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "paybox-db-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "paybox-jwt-secret"
  replication {
    auto {}
  }
}

# Artifact Registry
resource "google_artifact_registry_repository" "paybox" {
  location      = var.region
  repository_id = "paybox"
  description   = "Paybox Docker images"
  format        = "DOCKER"
}

# Cloud Monitoring
resource "google_monitoring_notification_channel" "email" {
  display_name = "Paybox Alerts"
  type         = "email"
  email_address = "alerts@paybox.example.com"
}

resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "Paybox Error Rate > 1%"
  combiner     = "OR"

  conditions {
    display_name = "Error rate condition"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" metric.label.\"error\"=\"true\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  alert_strategy {
    auto_close = "1800s"
  }
}

# Cloud Build trigger
resource "google_cloudbuild_trigger" "paybox_cicd" {
  name        = "paybox-deploy"
  description = "Deploy Paybox on code push"
  disabled    = false

  github {
    owner = "your-org"
    repo  = "paybox"
    push {
      branch = "^(main|release/.*)$"
    }
  }

  service_account = google_project_service.apis["cloudbuild.googleapis.com"].project != "" ? "your-sa@${var.project_id}.iam.gserviceaccount.com" : ""

  build {
    step {
      name = "gcr.io/cloud-builders/docker"
      args = ["build", "-t", "gcr.io/${_PROJECT_ID}/paybox:${COMMIT_SHA}", "."]
    }
    step {
      name = "gcr.io/cloud-builders/docker"
      args = ["push", "gcr.io/${_PROJECT_ID}/paybox:${COMMIT_SHA}"]
    }
    step {
      name = "gcr.io/cloud-builders/gke-deploy"
      args = ["apply", "-f", "k8s/", "-n", "paybox", "-e", "production"]
    }
  }
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

output "db_private_ip" {
  value = google_sql_database_instance.paybox_db.private_ip_address
}

output "redis_host" {
  value = google_redis_instance.paybox_redis.host
}

output "gke_cluster" {
  value = google_container_cluster.paybox_gke.name
}

output "artifact_registry" {
  value = google_artifact_registry_repository.paybox.id
}