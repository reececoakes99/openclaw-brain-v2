# AWS Infrastructure for Paybox Payment Gateway
# terraform 1.5+ | aws provider 5.x

variable "region" {
  description = "AWS Region"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 1.5"
  backend "s3" {
    bucket = "paybox-terraform-state"
    key    = "paybox/main.tf"
    region = var.region
  }
}

# VPC
resource "aws_vpc" "paybox" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "paybox-vpc-${var.environment}", Environment = var.environment }
}

# Subnets
resource "aws_subnet" "api_public" {
  vpc_id                  = aws_vpc.paybox.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = false
  tags = { Name = "paybox-api-public", Environment = var.environment }
}

resource "aws_subnet" "api_private" {
  vpc_id            = aws_vpc.paybox.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.region}a"
  tags = { Name = "paybox-api-private", Environment = var.environment }
}

resource "aws_subnet" "db" {
  vpc_id            = aws_vpc.paybox.id
  cidr_block        = "10.0.3.0/28"
  availability_zone = "${var.region}a"
  tags = { Name = "paybox-db", Environment = var.environment }
}

resource "aws_subnet" "hsm" {
  vpc_id            = aws_vpc.paybox.id
  cidr_block        = "10.0.4.0/28"
  availability_zone = "${var.region}a"
  tags = { Name = "paybox-hsm", Environment = var.environment }
}

# Internet Gateway
resource "aws_internet_gateway" "paybox" {
  vpc_id = aws_vpc.paybox.id
  tags = { Name = "paybox-igw", Environment = var.environment }
}

# NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"
}
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id      = aws_subnet.api_public.id
  tags = { Name = "paybox-nat", Environment = var.environment }
}

# Route Tables
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.paybox.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  tags = { Name = "paybox-private-rt", Environment = var.environment }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.paybox.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.paybox.id
  }
  tags = { Name = "paybox-public-rt", Environment = var.environment }
}
resource "aws_route_table_association" "api_private" {
  subnet_id      = aws_subnet.api_private.id
  route_table_id = aws_route_table.private.id
}
resource "aws_route_table_association" "db" {
  subnet_id      = aws_subnet.db.id
  route_table_id = aws_route_table.private.id
}
resource "aws_route_table_association" "hsm" {
  subnet_id      = aws_subnet.hsm.id
  route_table_id = aws_route_table.private.id
}

# EKS Cluster
resource "aws_eks_cluster" "paybox" {
  name     = "paybox-${var.environment}"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.29"

  vpc_config {
    subnet_ids              = [aws_subnet.api_public.id, aws_subnet.api_private.id]
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  depends_on = [aws_iam_role_policy_attachment.eks_cluster_policy]
}

resource "aws_iam_role" "eks_cluster" {
  name = "paybox-eks-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

# Node Groups
resource "aws_eks_node_group" "payment_api" {
  cluster_name    = aws_eks_cluster.paybox.name
  node_group_name = "payment-api"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = [aws_subnet.api_private.id]

  scaling_config {
    desired_size = 3
    max_size     = 20
    min_size     = 3
  }

  instance_types = ["m5.4xlarge"]
  capacity_type  = "ON_DEMAND"

  depends_on = [aws_iam_role_policy_attachment.workers_node_policy]
}

resource "aws_iam_role" "nodes" {
  name = "paybox-nodes"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "workers_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.nodes.name
}
resource "aws_iam_role_policy_attachment "ecr_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonECRContainerRegistryAccess"
  role       = aws_iam_role.nodes.name
}

# RDS PostgreSQL
resource "aws_db_subnet_group" "paybox" {
  name       = "paybox-db-subnet"
  subnet_ids = [aws_subnet.db.id]
}

resource "aws_db_instance" "paybox" {
  identifier           = "paybox-db-${var.environment}"
  engine              = "postgres"
  engine_version      = "15.4"
  instance_class      = "db.r5.2xlarge"
  allocated_storage   = 500
  storage_type        = "gp3"
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.db.arn
  db_name             = "paybox"
  username            = "paybox_admin"
  password            = random_password.db_password.result
  multi_az            = true
  db_subnet_group_name = aws_db_subnet_group.paybox.name
  vpc_security_group_ids = [aws_security_group.db.id]
  backup_retention_period = 7
  backup_window       = "03:00-04:00"
  maintenance_window  = "Mon:04:00-Mon:05:00"
  publicly_accessible = false
  skip_final_snapshot = true
}

resource "aws_kms_key" "db" {
  description = "Paybox DB encryption key"
  key_usage   = "ENCRYPT_DECRYPT"
  key_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { AWS = "*" }
      Action = "kms:*"
      Resource = "*"
    }]
  })
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "paybox" {
  name       = "paybox-redis-subnet"
  subnet_ids = [aws_subnet.api_private.id]
}

resource "aws_elasticache_replication_group" "paybox" {
  replication_group_id       = "paybox-redis-${var.environment}"
  engine                    = "redis"
  engine_version            = "7.0"
  node_type                 = "cache.r6g.large"
  number_cache_clusters     = 3
  parameter_group_name      = "default.redis7"
  port                      = 6379
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = true
  snapshot_retention_limit   = 7
  subnet_group_name         = aws_elasticache_subnet_group.paybox.name
  security_group_ids        = [aws_security_group.redis.id]
}

# ALB
resource "aws_lb" "paybox" {
  name               = "paybox-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.api_public.id]

  enable_deletion_protection = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    enabled = true
  }
}

resource "aws_lb_target_group" "api" {
  name     = "paybox-api-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = aws_vpc.paybox.id

  health_check {
    path            = "/health"
    port            = 8080
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.paybox.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate.paybox.arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ACM Certificate
resource "aws_acm_certificate" "paybox" {
  domain_name       = "api.paybox.example.com"
  validation_method = "DNS"
  subject_alternative_names = ["*.paybox.example.com"]
}

# WAF
resource "aws_wafv2_web_acl" "paybox" {
  name        = "paybox-waf"
  scope       = "REGIONAL"
  description = "Paybox WAF"

  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 1
    statement {
      managed_rule_statement {
        rule_group_reference {
          arn = "arn:aws:wafv2:eu-west-1:aws-managed:rule-group/SQLi"
        }
      }
    }
    action { block {} }
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 2
    statement {
      managed_rule_statement {
        rule_group_reference {
          arn = "arn:aws:wafv2:eu-west-1:aws-managed:rule-group/Common"
        }
      }
    }
    action { block {} }
  }

  default_action { allow {} }
}

resource "aws_wafv2_web_acl_association" "paybox" {
  resource_arn = aws_lb.paybox.arn
  web_acl_arn  = aws_wafv2_web_acl.paybox.arn
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "paybox-alb-sg"
  vpc_id      = aws_vpc.paybox.id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "api" {
  name        = "paybox-api-sg"
  vpc_id      = aws_vpc.paybox.id
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "db" {
  name        = "paybox-db-sg"
  vpc_id      = aws_vpc.paybox.id
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.paybox.cidr_block]
  }
}

resource "aws_security_group" "redis" {
  name        = "paybox-redis-sg"
  vpc_id      = aws_vpc.paybox.id
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.paybox.cidr_block]
  }
}

# S3 buckets
resource "aws_s3_bucket" "clearing_files" {
  bucket = "paybox-clearing-${var.environment}"
  versioning { enabled = true }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    }
  }
}

resource "aws_s3_bucket" "alb_logs" {
  bucket = "paybox-alb-logs-${var.environment}"
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = "paybox-terraform-state"
  versioning { enabled = true }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    }
  }
}

# Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  name = "paybox/db-password"
}
resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# CloudWatch Dashboard
resource "aws_cloudwatch_log_group" "paybox" {
  name              = "/paybox/${var.environment}"
  retention_in_days = 30
}

resource "aws_cloudwatch_dashboard" "paybox" {
  dashboard_name = "paybox-${var.environment}"

  widget {
    type = "metric"
    properties = jsonencode({
      metrics = [["Paybox", "TPS"], [".", "ErrorRate"], [".", "LatencyP99"]]
      period = 60
      stat = "Average"
      region = var.region
    })
  }
}

# Outputs
output "eks_cluster_name" {
  value = aws_eks_cluster.paybox.name
}
output "db_endpoint" {
  value = aws_db_instance.paybox.endpoint
}
output "redis_endpoint" {
  value = aws_elasticache_replication_group.paybox.primary_endpoint_address
}
output "alb_dns_name" {
  value = aws_lb.paybox.dns_name
}
output "waf_arn" {
  value = aws_wafv2_web_acl.paybox.arn
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "aws_iam_policy" "irsa" {
  name = "paybox-irsa-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.db_password.arn
      },
      {
        Effect = "Allow"
        Action = ["s3:*"]
        Resource = [aws_s3_bucket.clearing_files.arn, "${aws_s3_bucket.clearing_files.arn}/*"]
      }
    ]
  })
}