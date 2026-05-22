# Payment Gateway AWS Terraform — Main
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

terraform {
  required_version = ">= 1.5"
  backend "s3" {
    bucket = "neopay-terraform-state"
    key    = "payment-gateway/main.tf"
    region = var.region
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

# VPC
resource "aws_vpc" "payment" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "neopay-vpc-${var.environment}", Project = "Neopay", Environment = var.environment }
}

# Subnets
resource "aws_subnet" "public" {
  count             = 3
  vpc_id            = aws_vpc.payment.id
  cidr_block        = cidrsubnet(aws_vpc.payment.cidr_block, 4, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
  tags = { Name = "neopay-public-${count.index}", Environment = var.environment }
}

resource "aws_subnet" "private_app" {
  count             = 3
  vpc_id            = aws_vpc.payment.id
  cidr_block        = cidrsubnet(aws_vpc.payment.cidr_block, 4, count.index + 3)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "neopay-private-app-${count.index}", Environment = var.environment }
}

resource "aws_subnet" "private_db" {
  count             = 3
  vpc_id            = aws_vpc.payment.id
  cidr_block        = cidrsubnet(aws_vpc.payment.cidr_block, 4, count.index + 6)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "neopay-private-db-${count.index}", Environment = var.environment }
}

data "aws_availability_zones" "available" {}

# Internet Gateway + NAT
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.payment.id
  tags = { Name = "neopay-igw", Environment = var.environment }
}
resource "aws_eip" "nat" { domain = "vpc" }
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id      = aws_subnet.public[0].id
  tags = { Name = "neopay-nat", Environment = var.environment }
}

# Route tables
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.payment.id
  route  = [{ cidr_block = "0.0.0.0/0", nat_gateway_id = aws_nat_gateway.main.id }]
  tags = { Name = "neopay-private-rt", Environment = var.environment }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.payment.id
  route  = [{ cidr_block = "0.0.0.0/0", gateway_id = aws_internet_gateway.main.id }]
  tags = { Name = "neopay-public-rt", Environment = var.environment }
}
resource "aws_route_table_association" "private_app" {
  count          = 3
  subnet_id       = aws_subnet.private_app[count.index].id
  route_table_id  = aws_route_table.private.id
}
resource "aws_route_table_association" "private_db" {
  count          = 3
  subnet_id       = aws_subnet.private_db[count.index].id
  route_table_id  = aws_route_table.private.id
}
resource "aws_route_table_association" "public" {
  count          = 3
  subnet_id       = aws_subnet.public[count.index].id
  route_table_id  = aws_route_table.public.id
}

# EKS Cluster
resource "aws_eks_cluster" "neopay" {
  name     = "neopay-${var.environment}"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.29"

  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private_app[*].id)
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = ["0.0.0.0/0"]
  }

  kubernetes_network_config {
    ip_family = "ipv4"
    service_cidr = "172.20.0.0/16"
  }

  depends_on = [aws_iam_role_policy_attachment.eks_cluster_policy]
}

resource "aws_iam_role" "eks_cluster" {
  name = "neopay-eks-cluster"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "eks.amazonaws.com" } }] })
}
resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

# Node Groups
resource "aws_eks_node_group" "payment_engine" {
  cluster_name    = aws_eks_cluster.neopay.name
  node_group_name = "payment-engine"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = aws_subnet.private_app[*].id

  scaling_config {
    desired_size = 3
    max_size     = 50
    min_size     = 3
  }
  instance_types = ["m5.4xlarge"]
  capacity_type  = "ON_DEMAND"

  depends_on = [aws_iam_role_policy_attachment.workers_node_policy]
}

resource "aws_eks_node_group" "scheme_interface" {
  cluster_name    = aws_eks_cluster.neopay.name
  node_group_name = "scheme-interface"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = aws_subnet.private_app[*].id

  scaling_config {
    desired_size = 2
    max_size     = 20
    min_size     = 2
  }
  instance_types = ["m5.2xlarge"]

  depends_on = [aws_iam_role_policy_attachment.workers_node_policy]
}

resource "aws_iam_role" "nodes" {
  name = "neopay-nodes"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" } }] })
}
resource "aws_iam_role_policy_attachment" "workers_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.nodes.name
}
resource "aws_iam_role_policy_attachment" "ecr_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonECRContainerRegistryAccess"
  role       = aws_iam_role.nodes.name
}
resource "aws_iam_role_policy_attachment" "cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.nodes.name
}

# IAM Service Account
resource "aws_iam_role" "service_account" {
  name = "neopay-sa"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRoleWithWebIdentity", Effect = "Allow", Principal = { Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${aws_eks_cluster.neopay.identity.oidc.issuer}" }, Condition = { StringEquals = { "${aws_eks_cluster.neopay.identity.oidc.issuer}:sub" = "system:serviceaccount:payment-system:payment-engine" } } }] })
}
resource "aws_iam_role_policy" "irsa_policy" {
  name = "neopay-irsa"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = "*" },
      { Effect = "Allow", Action = ["s3:*"], Resource = ["arn:aws:s3:::neopay-clearing-*", "arn:aws:s3:::neopay-clearing-*/*"] },
      { Effect = "Allow", Action = ["kms:Encrypt", "kms:Decrypt"], Resource = "arn:aws:kms:*:${data.aws_caller_identity.current.account_id}:key/*" },
      { Effect = "Allow", Action = ["rds-db:connect"], Resource = "arn:aws:rds-db:*:${data.aws_caller_identity.current.account_id}:dbuser:*/neopay_app" }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "irsa" {
  policy_arn = aws_iam_role_policy.irsa_policy.arn
  role       = aws_iam_role.service_account.name
}

# Security Groups
resource "aws_security_group" "eks" {
  name        = "neopay-eks-sg"
  vpc_id      = aws_vpc.payment.id
  description = "EKS cluster security group"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.payment.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "hsm" {
  name        = "neopay-hsm-sg"
  vpc_id      = aws_vpc.payment.id
  description = "HSM connectivity"
  ingress {
    from_port   = 9999
    to_port     = 9999
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.payment.cidr_block]
  }
}

# Outputs
output "vpc_id" { value = aws_vpc.payment.id }
output "eks_cluster_name" { value = aws_eks_cluster.neopay.name }
output "eks_cluster_endpoint" { value = aws_eks_cluster.neopay.endpoint }
output "eks_oidc_issuer" { value = aws_eks_cluster.neopay.identity.oidc.issuer }