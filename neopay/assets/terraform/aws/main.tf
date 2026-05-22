# =============================================================================
# AWS Main Infrastructure for Neopay Payment Switch
# =============================================================================
# VPC, EKS Cluster, RDS PostgreSQL, ElastiCache Redis, CloudHSM, S3, IAM, CloudWatch
# Provider: AWS us-east-1 (primary) + us-west-2 (DR)

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.17"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
  # backend "s3" {
  #   bucket = "neopay-terraform-state"
  #   key    = "prod/main.tfstate"
  #   region = "us-east-1"
  #   dynamodb_table = "neopay-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "NeopayPaymentSwitch"
      ManagedBy   = "Terraform"
      Compliance  = "PCI-DSS"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "aws_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (prod/staging/dev)"
  type        = string
  default     = "prod"
}

variable "availability_zones" {
  description = "List of AZs for the VPC"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# =============================================================================
# VPC Configuration
# =============================================================================

resource "aws_vpc" "neopay_main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "neopay-${var.environment}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "neopay_igw" {
  vpc_id = aws_vpc.neopay_main.id

  tags = {
    Name = "neopay-${var.environment}-igw"
  }
}

# Public Subnets (Load Balancers, Bastion)
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.neopay_main.id
  cidr_block              = cidrsubnet(aws_vpc.neopay_main.cidr_block, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "neopay-${var.environment}-public-${var.availability_zones[count.index]}"
    Type = "Public"
  }
}

# Private Subnets (Application Tier - EKS Nodes)
resource "aws_subnet" "private_app" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.neopay_main.id
  cidr_block              = cidrsubnet(aws_vpc.neopay_main.cidr_block, 4, count.index + 4)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "neopay-${var.environment}-private-app-${var.availability_zones[count.index]}"
    Type = "Private-App"
  }
}

# Private Subnets (Data Tier - RDS, ElastiCache, CloudHSM)
resource "aws_subnet" "private_data" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.neopay_main.id
  cidr_block              = cidrsubnet(aws_vpc.neopay_main.cidr_block, 4, count.index + 8)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "neopay-${var.environment}-private-data-${var.availability_zones[count.index]}"
    Type = "Private-Data"
  }
}

# Subnet Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.neopay_main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.neopay_igw.id
  }

  tags = {
    Name = "neopay-${var.environment}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count = length(var.availability_zones)
  subnet_id = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# NAT Gateway for private subnets
resource "aws_eip" "nat_eip" {
  count  = length(var.availability_zones)
  domain = "vpc"
}

resource "aws_nat_gateway" "neopay_nat" {
  count      = length(var.availability_zones)
  subnet_id  = aws_subnet.public[count.index].id
  allocation_id = aws_eip.nat_eip[count.index].id

  tags = {
    Name = "neopay-${var.environment}-nat-${var.availability_zones[count.index]}"
  }
}

resource "aws_route_table" "private_app" {
  vpc_id = aws_vpc.neopay_main.id

  route {
    cidr_block             = "0.0.0.0/0"
    nat_gateway_id         = aws_nat_gateway.neopay_nat[0].id
  }

  tags = {
    Name = "neopay-${var.environment}-private-app-rt"
  }
}

resource "aws_route_table_association" "private_app" {
  count = length(var.availability_zones)
  subnet_id = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app.id
}

resource "aws_route_table" "private_data" {
  vpc_id = aws_vpc.neopay_main.id

  route {
    cidr_block             = "0.0.0.0/0"
    nat_gateway_id         = aws_nat_gateway.neopay_nat[0].id
  }

  tags = {
    Name = "neopay-${var.environment}-private-data-rt"
  }
}

resource "aws_route_table_association" "private_data" {
  count = length(var.availability_zones)
  subnet_id = aws_subnet.private_data[count.index].id
  route_table_id = aws_route_table.private_data.id
}

# =============================================================================
# Security Groups
# =============================================================================

# EKS Cluster Security Group
resource "aws_security_group" "eks_cluster" {
  name        = "neopay-${var.environment}-eks-cluster"
  description = "Security group for EKS cluster control plane"
  vpc_id      = aws_vpc.neopay_main.id

  ingress {
    description = "API server access from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "neopay-${var.environment}-eks-cluster-sg"
  }
}

# EKS Node Security Group
resource "aws_security_group" "eks_nodes" {
  name        = "neopay-${var.environment}-eks-nodes"
  description = "Security group for EKS worker nodes"
  vpc_id      = aws_vpc.neopay_main.id

  ingress {
    description = "API server to node kubelet"
    from_port   = 10250
    to_port     = 10250
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }
  ingress {
    description = "Node to node communication"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }
  ingress {
    description = "Inter-node traffic"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "neopay-${var.environment}-eks-nodes-sg"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name        = "neopay-${var.environment}-rds"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.neopay_main.id

  ingress {
    description = "PostgreSQL from EKS nodes"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }

  tags = {
    Name = "neopay-${var.environment}-rds-sg"
  }
}

# ElastiCache Security Group
resource "aws_security_group" "elasticache" {
  name        = "neopay-${var.environment}-elasticache"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.neopay_main.id

  ingress {
    description = "Redis from application tier"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }

  tags = {
    Name = "neopay-${var.environment}-elasticache-sg"
  }
}

# CloudHSM Security Group
resource "aws_security_group" "cloudhsm" {
  name        = "neopay-${var.environment}-cloudhsm"
  description = "Security group for AWS CloudHSM"
  vpc_id      = aws_vpc.neopay_main.id

  ingress {
    description = "HSM traffic from application tier"
    from_port   = 2223
    to_port     = 2223
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.neopay_main.cidr_block]
  }

  tags = {
    Name = "neopay-${var.environment}-cloudhsm-sg"
  }
}

# =============================================================================
# RDS PostgreSQL (Primary Transaction Database)
# =============================================================================

resource "aws_db_subnet_group" "neopay_rds" {
  name       = "neopay-${var.environment}-rds-subnet"
  subnet_ids = aws_subnet.private_data[*].id

  tags = {
    Name = "neopay-${var.environment}-rds-subnet-group"
  }
}

resource "aws_rds_cluster" "neopay_postgres" {
  cluster_identifier  = "neopay-${var.environment}-postgres"
  engine              = "aurora-postgresql"
  engine_version      = "15.4"
  engine_mode         = "provisioned"
  master_username     = "neopayadmin"
  master_password     = random_password.rds_password.result
  db_subnet_group_name = aws_db_subnet_group.neopay_rds.name
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.rds.arn

  serverlessv2_scaling_configuration {
    max_capacity = 128.0
    min_capacity = 8.0
  }

  backup_retention_period = 30
  preferred_backup_window = "03:00-04:00"
  preferred_maintenance_window = "mon:04:00-mon:05:00"

  tags = {
    Name = "neopay-${var.environment}-postgres-cluster"
  }
}

resource "random_password" "rds_password" {
  length  = 32
  special = true
}

resource "aws_kms_key" "rds" {
  description = "KMS key for RDS encryption at rest"
  key_usage   = "ENCRYPT_DECRYPT"

  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "neopay-${var.environment}-rds-kms"
  }
}

# =============================================================================
# ElastiCache Redis (Session, Rate Limiting, Cache)
# =============================================================================

resource "aws_elasticache_subnet_group" "neopay_redis" {
  name       = "neopay-${var.environment}-redis-subnet"
  subnet_ids = aws_subnet.private_data[*].id
}

resource "aws_elasticache_replication_group" "neopay_redis" {
  replication_group_id       = "neopay-${var.environment}-redis"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.r6g.4xlarge"
  number_cache_clusters      = length(var.availability_zones)
  multi_az_enabled           = true
  automatic_failover_enabled = true
  auto_minor_version_upgrade = true

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = true
  encryption_key             = aws_kms_key.redis.arn

  cache_subnet_group_name   = aws_elasticache_subnet_group.neopay_redis.name
  security_group_ids        = [aws_security_group.elasticache.id]

  backup_retention_limit = 30
  preferred_backup_window = "02:00-03:00"

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow.id
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  tags = {
    Name = "neopay-${var.environment}-redis-cluster"
  }
}

resource "aws_kms_key" "redis" {
  description = "KMS key for ElastiCache encryption at rest"
  key_usage   = "ENCRYPT_DECRYPT"

  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_cloudwatch_log_group" "redis_slow" {
  name              = "/aws/elasticache/neopay-${var.environment}/redis/slow-log"
  retention_in_days = 30
}

# =============================================================================
# AWS CloudHSM (Cryptographic Module)
# =============================================================================

resource "aws_cloudhsm_v2_cluster" "neopay_hsm" {
  hsm_type    = "hsm1.medium"
  subnet_ids  = aws_subnet.private_data[*].id
  cluster_type = "cluster-e3"

  tags = {
    Name = "neopay-${var.environment}-cloudhsm-cluster"
  }
}

resource "aws_cloudhsm_v2_hsm" "neopay_hsm" {
  count         = length(var.availability_zones)
  cluster_id    = aws_cloudhsm_v2_cluster.neopay_hsm.cluster_id
  subnet_id     = aws_subnet.private_data[count.index].id
  availability_zone = var.availability_zones[count.index]
}

resource "aws_cloudhsm_v2_cluster" "neopay_hsm_dr" {
  count        = var.environment == "prod" ? 1 : 0
  hsm_type     = "hsm1.medium"
  subnet_ids   = aws_subnet.private_data[*].id
  cluster_type = "cluster-e3"

  tags = {
    Name = "neopay-${var.environment}-cloudhsm-cluster-dr"
  }
}

# =============================================================================
# S3 Buckets
# =============================================================================

resource "aws_s3_bucket" "neopay_artifacts" {
  bucket = "neopay-${var.environment}-artifacts"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
        kms_key_id   = aws_kms_key.s3_artifacts.arn
      }
    }
  }

  lifecycle_rule {
    id      = "archive-old-versions"
    enabled = true

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  tags = {
    Name = "neopay-${var.environment}-artifacts-bucket"
  }
}

resource "aws_s3_bucket" "neopay_transaction_logs" {
  bucket = "neopay-${var.environment}-txn-logs"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
        kms_key_id   = aws_kms_key.s3_logs.arn
      }
    }
  }

  lifecycle_rule {
    id      = "archive-transaction-logs"
    enabled = true

    filter {
      prefix = "raw/"
    }

    transitions {
      days          = 7
      storage_class = "STANDARD_IA"
    }

    transitions {
      days          = 30
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }

  tags = {
    Name = "neopay-${var.environment}-txn-logs-bucket"
  }
}

resource "aws_s3_bucket" "neopay_hsm_audit" {
  bucket = "neopay-${var.environment}-hsm-audit"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
        kms_key_id   = aws_kms_key.s3_logs.arn
      }
    }
  }

  lifecycle_rule {
    id      = "audit-retention"
    enabled = true
    expiration {
      days = 2555  # 7 years for PCI-DSS compliance
    }
  }

  tags = {
    Name = "neopay-${var.environment}-hsm-audit-bucket"
  }
}

resource "aws_s3_bucket" "neopay_backups" {
  bucket = "neopay-${var.environment}-backups"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
        kms_key_id   = aws_kms_key.s3_backups.arn
      }
    }
  }

  lifecycle_rule {
    id      = "backup-retention"
    enabled = true
    expiration {
      days = 90
    }
  }

  tags = {
    Name = "neopay-${var.environment}-backups-bucket"
  }
}

resource "aws_kms_key" "s3_artifacts" {
  description = "KMS key for S3 artifacts bucket"
  key_usage   = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "s3_logs" {
  description = "KMS key for S3 logs bucket"
  key_usage   = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "s3_backups" {
  description = "KMS key for S3 backups bucket"
  key_usage   = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# S3 Access Points for IAM policies
resource "aws_s3_access_point" "neopay_artifacts_ap" {
  bucket = aws_s3_bucket.neopay_artifacts.id
  name   = "neopay-${var.environment}-artifacts-ap"

  vpc_configuration {
    vpc_id = aws_vpc.neopay_main.id
  }
}

# =============================================================================
# IAM Roles and Policies
# =============================================================================

# EKS Node Role
resource "aws_iam_role" "eks_node_role" {
  name = "neopay-${var.environment}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_amazon_eks_cni_policy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_node_amazon_eks_worker_node_policy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_node_amazon_eks_container_registry_readonly" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_node_custom" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = aws_iam_policy.eks_node_custom.name
}

resource "aws_iam_policy" "eks_node_custom" {
  name = "neopay-${var.environment}-eks-node-custom-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.neopay_artifacts.arn,
          "${aws_s3_bucket.neopay_artifacts.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudhsm:DescribeClusters",
          "cloudhsm:DescribeHsm"
        ]
        Resource = aws_cloudhsm_v2_cluster.neopay_hsm.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "rds:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# Service Account Role (IRSA)
resource "aws_iam_role" "neopay_service_account" {
  name = "neopay-${var.environment}-service-account"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${aws_iam_openid_connect_provider.neopay_oidc.url}"
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${aws_iam_openid_connect_provider.neopay_oidc.url}:sub" = "system:serviceaccount:neopay:${var.environment}-service-account"
        }
      }
    }]
  })
}

resource "aws_iam_openid_connect_provider" "neopay_oidc" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a5464dcd1d33a0fce4c5e0f1a5b1e8e8c5f4"]  # Replace with actual thumbprint
}

# EKS Cluster Role
resource "aws_iam_role" "eks_cluster_role" {
  name = "neopay-${var.environment}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_amazon_eks_cluster_policy" {
  role       = aws_iam_role.eks_cluster_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cluster_amazon_eks_service_policy" {
  role       = aws_iam_role.eks_cluster_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSServicePolicy"
}

# =============================================================================
# CloudWatch
# =============================================================================

resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/neopay-${var.environment}/cluster"
  retention_in_days = 90
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/neopay/${var.environment}/application"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "hsm_audit" {
  name              = "/neopay/${var.environment}/hsm/audit"
  retention_in_days = 2555  # 7 years for PCI-DSS
}

resource "aws_cloudwatch_dashboard" "neopay_overview" {
  dashboard_name = "neopay-${var.environment}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title = "Payment Transaction Rate"
          region = var.aws_region
          stat = "Sum"
          period = 60
          metrics = [["Neopay/Payment", "Transactions", "Environment", var.environment]]
        }
      }
    ]
  })
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}

# =============================================================================
# Outputs
# =============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.neopay_main.id
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.neopay_eks.cluster_endpoint
}

output "eks_cluster_ca" {
  description = "EKS cluster certificate authority"
  value       = aws_eks_cluster.neopay_eks.certificate_authority[0].data
  sensitive   = true
}

output "rds_endpoint" {
  description = "RDS cluster endpoint"
  value       = aws_rds_cluster.neopay_postgres.endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_replication_group.neopay_redis.primary_endpoint_address
}

output "cloudhsm_cluster_id" {
  description = "CloudHSM cluster ID"
  value       = aws_cloudhsm_v2_cluster.neopay_hsm.cluster_id
}
