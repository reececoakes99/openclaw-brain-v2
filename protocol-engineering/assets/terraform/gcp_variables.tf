# GCP Variables for protocol-engineering Terraform
# Place in same directory as gcp_main.tf, gcp_eks.tf, gcp_security.tf

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all regional resources"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Environment: dev, staging, prod"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/8"
}

variable "sql_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-n1-standard-4"
}

variable "redis_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 6
}

variable "cluster_node_count" {
  description = "Initial node count for GKE cluster"
  type        = number
  default     = 3
}

variable "hsm_node_count" {
  description = "Initial HSM gateway node pool count"
  type        = number
  default     = 1
}

variable "enable_binary_authorization" {
  description = "Enable binary authorization for GKE"
  type        = bool
  default     = true
}

variable "enable_vpc_sc" {
  description = "Enable VPC Service Controls"
  type        = bool
  default     = true
}

variable "sql_replica_count" {
  description = "Number of SQL read replicas"
  type        = number
  default     = 2
}

variable "redis_replica_count" {
  description = "Number of Redis replicas"
  type        = number
  default     = 2
}

variable "k8s_release_channel" {
  description = "GKE release channel: rapid, regular, stable"
  type        = string
  default     = "regular"
}

locals {
  environment_labels = {
    dev     = { env = "dev", criticality = "low" }
    staging = { env = "staging", criticality = "medium" }
    prod    = { env = "prod", criticality = "high" }
  }
}