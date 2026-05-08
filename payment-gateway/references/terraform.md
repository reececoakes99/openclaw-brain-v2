# Terraform Deployment Guide for Payment Gateway

AWS infrastructure as code for enterprise payment gateway deployment using Terraform 1.5+ and AWS Provider 5.x.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              AWS REGION                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                           VPC (10.0.0.0/16)                              │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │                    TRANSIT GATEWAY                                │   │ │
│  │  │              (Multi-VPC Connectivity)                             │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                         │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │ │
│  │  │   PUBLIC SN     │  │   PRIVATE SN   │  │  MANAGEMENT SN │           │ │
│  │  │  (ALB, WAF)     │  │ (EKS Workers)  │  │ (Bastion, VPN) │           │ │
│  │  │  10.0.1.0/24    │  │  10.0.2.0/24   │  │  10.0.3.0/24   │           │ │
│  │  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘           │ │
│  │          │                    │                    │                    │ │
│  │  ┌───────▼────────────────────▼────────────────────▼────────┐         │ │
│  │  │                    EKS CLUSTER (payment-engine)             │         │ │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │         │ │
│  │  │  │ message-engine│ │   vault-svc  │ │   hsm-svc    │       │         │ │
│  │  │  │  m5.4xlarge   │ │  m5.xlarge   │ │  r5.2xlarge  │       │         │ │
│  │  │  │   (3-50)      │ │   (2-20)     │ │   (2-10)     │       │         │ │
│  │  │  └──────────────┘ └──────────────┘ └──────────────┘       │         │ │
│  │  └───────────────────────────────────────────────────────────┘         │ │
│  │                                                                         │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │ │
│  │  │  RDS Oracle    │  │ ElastiCache    │  │    S3         │           │ │
│  │  │ Multi-AZ      │  │ Redis Cluster  │  │ Clearing Files│           │ │
│  │  │db.r5.4xlarge  │  │ 3 shards x 3   │  │   & Backups   │           │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘           │ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────┐    │ │
│  │  │              ACM Certificates + Route 53                       │    │ │
│  │  └───────────────────────────────────────────────────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Main Terraform Module

### providers.tf

```hcl
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }

  backend "s3" {
    bucket = "paybox-terraform-state"
    key    = "payment-gateway/terraform.tfstate"
    region = "eu-west-1"
    dynamodb_table = "paybox-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = var.environment
      Project     = "payment-gateway"
      ManagedBy   = "terraform"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}
```

### variables.tf

```hcl
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for deployment"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r5.4xlarge"
}

variable "db_storage_gb" {
  description = "Database storage in GB"
  type        = number
  default     = 500
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.r5.large"
}

variable "eks_worker_node_count" {
  description = "EKS worker node count"
  type        = map(string)
  default = {
    message-engine = "3-50"
    vault-service  = "2-20"
    hsm-service    = "2-10"
  }
}
```

## EKS Cluster Module

```hcl
# eks.tf

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "payment-engine"
  cluster_version = "1.28"
  
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  # EKS Add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }

  # EKS Managed Node Groups
  eks_managed_node_groups = {
    message-engine = {
      name = "message-engine"
      
      instance_types = ["m5.4xlarge"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 3
      max_size     = 50
      desired_size = 5

      key_name = "paybox-prod-key"
      
      labels = {
        workload = "message-engine"
      }
      
      taints = []
      
      update_config {
        max_unavailable_percentage = 25
      }
    }
    
    vault-service = {
      name = "vault-service"
      
      instance_types = ["m5.xlarge"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 2
      max_size     = 20
      desired_size = 3
      
      key_name = "paybox-prod-key"
      
      labels = {
        workload = "vault-service"
      }
      
      taints = [{
        key    = "workload"
        value  = "sensitive"
        effect = "NO_SCHEDULE"
      }]
    }
    
    hsm-service = {
      name = "hsm-service"
      
      instance_types = ["r5.2xlarge"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 2
      max_size     = 10
      desired_size = 2
      
      key_name = "paybox-prod-key"
      
      labels = {
        workload = "hsm-service"
      }
      
      taints = [{
        key    = "workload"
        value  = "hsm"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  # Security groups
  node_security_group_rules = {
    ingress_nodes = {
      type                          = "ingress"
      source_cluster_security_group = true
      description                   = "Node to node ingress"
    }
  }

  # IRSA for service accounts
  enable_irsa = true

  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}
```

## Security Configuration

```hcl
# security.tf

# VPC Module
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "payment-gateway-vpc"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = ["10.0.2.0/24", "10.0.3.0/24", "10.0.4.0/24"]
  public_subnets  = ["10.0.1.0/24", "10.0.5.0/24", "10.0.6.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false

  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

# Security Group for EKS Cluster
resource "aws_security_group" "eks_cluster" {
  name        = "payment-gateway-eks-cluster"
  description = "Security group for EKS cluster"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTPS from ALB"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.1.0/24"]
  }

  egress {
    description = "HTTPS to internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "payment-gateway-eks-cluster"
  }
}

# Security Group for Database
resource "aws_security_group" "rds" {
  name        = "payment-gateway-rds"
  description = "Security group for RDS Oracle"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Oracle SQLNet from private subnets"
    from_port       = 1521
    to_port         = 1521
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_cluster.id]
  }

  tags = {
    Name = "payment-gateway-rds"
  }
}

# Security Group for ElastiCache
resource "aws_security_group" "redis" {
  name        = "payment-gateway-redis"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Redis from private subnets"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_cluster.id]
  }

  tags = {
    Name = "payment-gateway-redis"
  }
}
```

## RDS Oracle Module

```hcl
# rds.tf

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "payment-gateway-db"

  engine               = "oracle-ee"
  engine_version       = "19.0.0.0.0.ru-2023-10.r1"
  family               = "oracle-19"
  major_engine_version = "19"
  
  instance_class    = var.db_instance_class
  allocated_storage = var.db_storage_gb
  max_allocated_storage = 2000
  storage_type      = "gp3"
  storage_throughput = 1000
  
  multi_az               = true
  availability_zone      = var.availability_zones[0]
  secondary_availability_zone = var.availability_zones[1]
  
  db_name  = "paybox"
  username = "paybox_admin"
  port     = 1521
  
  # Use Secrets Manager for password
  manage_master_user_password = false
  master_user_password_secret_arn = aws_secretsmanager_secret.db_password.arn
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  license_model          = "bring-your-own-license"
  option_group_name      = aws_db_option_group.main.name
  parameter_group_name   = aws_db_parameter_group.main.name
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"
  
  enabled_cloudwatch_logs_exports = ["alert", "audit", "general"]
  
  delete_automated_backups = false
  
  skip_final_snapshot       = false
  final_snapshot_identifier = "payment-gateway-final-snapshot"
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "payment-gateway-db-subnet"
  subnet_ids = module.vpc.private_subnets
  
  tags = {
    Name = "payment-gateway-db-subnet"
  }
}

resource "aws_db_option_group" "main" {
  name                 = "payment-gateway-db-options"
  engine_name         = "oracle-ee"
  major_engine_version = "19"
  
  option {
    option_name = "OEM"
  }
}

resource "aws_db_parameter_group" "main" {
  name   = "payment-gateway-db-params"
  family = "oracle-19"
  
  parameter {
    name  = "max_connections"
    value = "1000"
  }
  
  parameter {
    name  = "audit_trail"
    value = "DB_EXTENDED"
  }
  
  parameter {
    name  = "sql_trace"
    value = "false"
  }
}

resource "aws_secretsmanager_secret" "db_password" {
  name        = "payment-gateway-db-password"
  description = "Database master password for payment gateway"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  
  secret_string = random_password.db_password.result
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!@#$%*"
}
```

## ElastiCache Redis Module

```hcl
# redis.tf

module "redis" {
  source  = "terraform-aws-modules/elasticache/aws"
  version = "~> 8.0"

  replication_group_id        = "payment-gateway-redis"
  replication_group_description = "Payment gateway Redis cluster"
  
  engine                          = "redis"
  engine_version                  = "7.0"
  auto_minor_version_upgrade      = true
  
  node_type            = var.redis_node_type
  number_cache_clusters = 3
  
  port                 = 6379
  
  multi_az_enabled = true
  automatic_failover_enabled = true
  
  # Cluster mode configuration
  cluster_mode_enabled = true
  num_node_groups = 3
  replicas_per_node_group = 3
  
  # Security
  security_group_ids = [aws_security_group.redis.id]
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  
  # Encryption at rest
  at_rest_encryption_enabled = true
  kms_key_id = aws_kms_key.redis.arn
  
  # Encryption in transit
  transit_encryption_enabled = true
  auth_token_enabled = true
  
  # Backup configuration
  snapshot_retention_limit   = 30
  snapshot_window           = "03:00-04:00"
  maintenance_window        = "mon:04:00-mon:05:00"
  auto_minor_version_upgrade = true
  
  # Log delivery
  log_delivery_configuration = [
    {
      destination      = aws_cloudwatch_log_group.redis_slow.name
      destination_type = "cloudwatch-logs"
      log_format       = "json"
      log_type         = "slow-log"
    }
  ]
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "payment-gateway-redis-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_kms_key" "redis" {
  description = "KMS key for Redis at-rest encryption"
  key_usage   = "ENCRYPT_DECRYPT"
  
  deletion_window_in_days = 7
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_cloudwatch_log_group" "redis_slow" {
  name              = "/aws/elasticache/payment-gateway/slow-log"
  retention_in_days = 30
}
```

## Application Load Balancer

```hcl
# alb.tf

module "alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 8.0"

  name = "payment-gateway-alb"
  
  load_balancer_type = "application"
  internal           = false
  
  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnets
  
  security_groups = [aws_security_group.alb.id]
  
  # HTTP to HTTPS redirect
  http_tcp_listeners = [
    {
      port           = 80
      protocol       = "HTTP"
      action_type    = "redirect"
      redirect = {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  ]
  
  https_listeners = [
    {
      port               = 443
      protocol           = "HTTPS"
      certificate_arn    = module.acm.acm_certificate_arn
      ssl_policy         = "ELBSecurityPolicy-TLS13-1-2-2021-06"
      action_type        = "forward"
      target_group_index = 0
    }
  ]
  
  target_groups = [
    {
      name              = "payment-api-tg"
      port              = 8080
      protocol          = "HTTP"
      target_type       = "ip"
      deregistration_delay = 30
      
      health_check = {
        enabled             = true
        path                = "/health"
        port                = "traffic-port"
        healthy_threshold   = 2
        unhealthy_threshold = 3
        timeout             = 10
        interval            = 15
        matcher             = "200"
      }
      
      stickiness = {
        enabled         = true
        type            = "lb_cookie"
        cookie_duration = 3600
      }
    }
  ]
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_security_group" "alb" {
  name        = "payment-gateway-alb"
  description = "Security group for ALB"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    description = "HTTP to targets"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }
}
```

## IAM Roles for Service Accounts

```hcl
# iam.tf

data "aws_iam_policy_document" "message_engine_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
    
    actions = ["sts:AssumeRoleWithWebIdentity"]
    
    condition {
      test     = "StringEquals"
      variable = "${aws iam role for service accounts}"
      values   = ["payment-gateway.message-engine"]
    }
  }
}

resource "aws_iam_role" "message_engine" {
  name = "payment-gateway-message-engine"
  
  assume_role_policy = data.aws_iam_policy_document.message_engine_assume_role.json
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_iam_role_policy_attachment" "message_engine_vault" {
  role       = aws_iam_role.message_engine.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
}

resource "aws_iam_role_policy_attachment" "message_engine_s3" {
  role       = aws_iam_role.message_engine.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_policy" "s3_access" {
  name        = "payment-gateway-s3-access"
  description = "S3 access policy for payment gateway"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${module.s3_clearing.arn}/*",
          "${module.s3_backups.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          module.s3_clearing.arn,
          module.s3_backups.arn
        ]
      }
    ]
  })
}

# S3 Buckets
module "s3_clearing" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 3.0"

  bucket = "payment-gateway-clearing-files-${var.environment}"
  
  versioning = {
    enabled = true
  }
  
  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }
  
  lifecycle_rule = {
    enabled = true
    transition = [
      { days = 30, storage_class = "STANDARD_IA" },
      { days = 90, storage_class = "GLACIER" }
    ]
    expiration = { days = 365 }
  }
}

module "s3_backups" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 3.0"

  bucket = "payment-gateway-db-backups-${var.environment}"
  
  versioning = {
    enabled = true
  }
  
  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }
  
  lifecycle_rule = {
    enabled = true
    noncurrent_version_transition = [
      { days = 7, storage_class = "GLACIER" }
    ]
    noncurrent_version_expiration = { days = 30 }
  }
}
```

## ECR Repositories

```hcl
# ecr.tf

locals {
  services = ["message-engine", "vault-service", "hsmm-service", "psd2-gateway", "rest-api", "settlement", "fraud-engine"]
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.services)
  
  name                 = "payment-gateway/${each.value}"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration = {
    scan_on_push = true
  }
  
  encryption_configuration = {
    encryption_type = "AES256"
  }
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
    Service     = each.value
  }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each = aws_ecr_repository.services
  
  repository = each.value.name
  
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["v"]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
```

## Secrets Manager

```hcl
# secrets.tf

resource "aws_secretsmanager_secret" "hsm_credentials" {
  name        = "payment-gateway/hsm/credentials"
  description = "HSM credentials for payment gateway"
  
  recovery_window_in_days = 7
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "payment-gateway/jwt/secret"
  description = "JWT signing secret for payment gateway"
  
  recovery_window_in_days = 7
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_secretsmanager_secret" "api_keys" {
  name        = "payment-gateway/api/keys"
  description = "API keys for external integrations"
  
  recovery_window_in_days = 7
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_secretsmanager_secret" "webhook_signing_keys" {
  name        = "payment-gateway/webhook/signing-keys"
  description = "Webhook signing keys for merchant callbacks"
  
  recovery_window_in_days = 7
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

# Secrets Manager Secret Rotation via Lambda
resource "aws_secretsmanager_secret_rotation" "hsm_credentials" {
  secret_id = aws_secretsmanager_secret.hsm_credentials.id
  
  rotation_lambda_arn = module.lambda_rotation.function_arn
  
  rotation_rules {
    automatically_after_days = 30
  }
}
```

## ACM Certificates

```hcl
# certificates.tf

resource "aws_acm_certificate" "main" {
  domain_name               = "api.paybox.example.com"
  validation_method        = "DNS"
  subject_alternative_names = [
    "*.paybox.example.com"
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_acm_certificate" "internal" {
  domain_name           = "internal.paybox.example.com"
  validation_method    = "DNS"
  domain_validation_options = [
    {
      domain_name = "internal.paybox.example.com"
      validation_domain = "paybox.example.com"
    }
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}
```

## Monitoring

```hcl
# monitoring.tf

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "payment_gateway" {
  dashboard_name = "payment-gateway-${var.environment}"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["payment-gateway", "transaction_count", { stat = "Sum" }],
            [".", "transaction_amount_sum", { stat = "Sum" }],
            [".", "authorization_rate", { stat = "Average" }]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Transaction Metrics"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["payment-gateway", "api_latency_p99", { stat = "p99" }],
            [".", "api_latency_p95", { stat = "p95" }],
            [".", "api_latency_p50", { stat = "p50" }]
          ]
          period = 60
          stat   = "p99"
          region = var.aws_region
          title  = "API Latency"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["payment-gateway", "error_rate", { stat = "Average" }],
            [".", "hsm_error_rate", { stat = "Average" }]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Error Rates"
        }
      }
    ]
  })
}

# X-Ray Daemon configuration
resource "aws_ecs_task_definition" "xray_daemon" {
  family                   = "payment-gateway-xray"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = "256"
  memory                  = "512"
  
  container_definitions = [{
    name      = "xray-daemon"
    image     = "amazon/aws-xray-daemon:latest"
    essential = false
    
    environment = [{
      name  = "AWS_REGION"
      value = var.aws_region
    }]
    
    log_configuration = {
      log_driver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/payment-gateway/xray"
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }]
}
```

## Transit Gateway

```hcl
# transit_gateway.tf

module "transit_gateway" {
  source  = "terraform-aws-modules/transit-gateway/aws"
  version = "~> 3.0"

  name = "payment-gateway-tgw"
  
  enable_shared_sds = false
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

# Attach VPC to Transit Gateway
resource "aws_ec2_transit_gateway_vpc_attachment" "main" {
  transit_gateway_id = module.transit_gateway.id
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnets
  
  dns_support            = "enable"
  ipv6_support           = "disable"
  appliance_mode_support = "disable"
}

# Route Table for VPC
resource "aws_vpc_endpoint" "s3" {
  vpc_id           = module.vpc.vpc_id
  service_name     = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  
  route_table_ids = [module.vpc.default_route_table_id]
}
```

## Route 53

```hcl
# route53.tf

resource "aws_route53_zone" "main" {
  name = "paybox.example.com"
  
  vpc {
    vpc_id = module.vpc.vpc_id
  }
  
  tags = {
    Environment = var.environment
    Project     = "payment-gateway"
  }
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.paybox.example.com"
  type    = "A"
  
  alias {
    name                   = module.alb.lb_dns_name
    zone_id                = module.alb.lb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "health" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "health.paybox.example.com"
  type    = "A"
  
  alias {
    name                   = module.alb.lb_dns_name
    zone_id                = module.alb.lb_zone_id
    evaluate_target_health = true
  }
}
```

## Deployment Commands

```bash
# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file="environments/prod.tfvars" -out=tfplan

# Apply deployment
terraform apply tfplan

# Verify deployment
kubectl get nodes -o wide
kubectl get pods -A

# Check EKS cluster
aws eks update-kubeconfig --region eu-west-1 --name payment-engine
kubectl config current-context
```
