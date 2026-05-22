# =============================================================================
# AWS EKS Cluster and Node Groups for Neopay Payment Switch
# =============================================================================
# EKS Cluster, Fargate Profiles, Managed Node Groups (System, Processing, HSM)
# Kubernetes version: 1.29
# Node OS: Amazon Linux 2023 (AL2023) or Bottlerocket

# =============================================================================
# EKS Cluster
# =============================================================================

resource "aws_eks_cluster" "neopay_eks" {
  name     = "neopay-${var.environment}-eks"
  role_arn = aws_iam_role.eks_cluster_role.arn
  version  = "1.29"

  vpc_config {
    subnet_ids              = concat(aws_subnet.private_app[*].id, aws_subnet.private_data[*].id)
    cluster_security_group_id = aws_security_group.eks_cluster.id
    endpoint_private_access = true
    endpoint_public_access  = false
    public_access_cidrs    = []

    # Enable VPC Flow Logs for network monitoring
    logging {
      api = true
      audit = true
      authenticator = true
      controller_manager = false
      scheduler = false
    }
  }

  kubernetes_network_config {
    service_ipv4_cidr = "172.20.0.0/16"
    ip_family        = "ipv4"
  }

  # Enable EKS encryption with KMS
  encryption_config {
    provider {
      key_arn = aws_kms_key.eks_cluster.arn
    }
    resources = ["secrets"]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_amazon_eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_cluster_amazon_eks_service_policy,
    aws_cloudwatch_log_group.eks_cluster
  ]

  tags = {
    Name = "neopay-${var.environment}-eks-cluster"
  }
}

resource "aws_kms_key" "eks_cluster" {
  description = "KMS key for EKS secrets encryption"
  key_usage   = "ENCRYPT_DECRYPT"

  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "neopay-${var.environment}-eks-kms"
  }
}

# =============================================================================
# Fargate Profile (Serverless Workloads)
# =============================================================================
# Used for: API Gateway pods, webhook processors, lightweight background tasks

resource "aws_eks_fargate_profile" "serverless" {
  cluster_name           = aws_eks_cluster.neopay_eks.name
  fargate_profile_name   = "serverless"
  pod_execution_role_arn = aws_iam_role.fargate_pod_execution.name
  subnet_ids            = aws_subnet.private_app[*].id

  selector {
    namespace = "serverless"
    labels = {
      workload-type = "serverless"
    }
  }

  selector {
    namespace = "webhooks"
    labels = {
      workload-type = "serverless"
    }
  }

  tags = {
    Name = "neopay-${var.environment}-fargate-serverless"
  }
}

resource "aws_iam_role" "fargate_pod_execution" {
  name = "neopay-${var.environment}-fargate-pod-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "eks-fargate-pods.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "fargate_pod_execution" {
  role       = aws_iam_role.fargate_pod_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
}

# =============================================================================
# Managed Node Group: System Nodes
# =============================================================================
# Core Kubernetes system pods (CoreDNS, kube-proxy, VPC CNI, metrics-server)
# m6i.4xlarge: 16 vCPU, 64 GB RAM

resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.neopay_eks.name
  node_group_name = "system-nodes"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = aws_subnet.private_app[*].id
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = 3
    max_size     = 6
    min_size     = 3
  }

  instance_types = ["m6i.4xlarge"]

  launch_template {
    id      = aws_launch_template.system.id
    version = aws_launch_template.system.latest_version
  }

  labels = {
    "node-type" = "system"
    "workload-type" = "core"
  }

  taints {
    key    = "node-type"
    value  = "system"
    effect = "NO_SCHEDULE"
  }

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name = "neopay-${var.environment}-system-nodes"
  }
}

# =============================================================================
# Managed Node Group: Processing Nodes
# =============================================================================
# Message engine, authorization host, ISO8583 parser, HSM workers
# r6i.8xlarge: 32 vCPU, 256 GB RAM, high network throughput

resource "aws_eks_node_group" "processing" {
  cluster_name    = aws_eks_cluster.neopay_eks.name
  node_group_name = "processing-nodes"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = aws_subnet.private_app[*].id
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = 6
    max_size     = 24
    min_size     = 3
  }

  instance_types = ["r6i.8xlarge"]

  launch_template {
    id      = aws_launch_template.processing.id
    version = aws_launch_template.processing.latest_version
  }

  labels = {
    "node-type" = "processing"
    "workload-type" = "message-engine"
    "tier" = "payment-critical"
  }

  taints {
    key    = "workload-type"
    value  = "message-engine"
    effect = "NO_SCHEDULE"
  }

  update_config {
    max_unavailable_percentage = 10
  }

  tags = {
    Name = "neopay-${var.environment}-processing-nodes"
  }
}

# =============================================================================
# Managed Node Group: HSM Nodes
# =============================================================================
# HSM command processors, cryptographic operations
# Dedicated instances for HSM connectivity (low latency required)
# c6i.4xlarge: 16 vCPU, 32 GB RAM

resource "aws_eks_node_group" "hsm_workers" {
  cluster_name    = aws_eks_cluster.neopay_eks.name
  node_group_name = "hsm-nodes"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = aws_subnet.private_data[*].id
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = 3
    max_size     = 6
    min_size     = 2
  }

  instance_types = ["c6i.4xlarge"]

  launch_template {
    id      = aws_launch_template.hsm.id
    version = aws_launch_template.hsm.latest_version
  }

  labels = {
    "node-type" = "hsm"
    "workload-type" = "cryptographic"
    "tier" = "payment-critical"
  }

  taints {
    key    = "workload-type"
    value  = "cryptographic"
    effect = "NO_SCHEDULE"
  }

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name = "neopay-${var.environment}-hsm-nodes"
  }
}

# =============================================================================
# Managed Node Group: Database Proxy Nodes
# =============================================================================
# PgBouncer, RDS proxy, database connection pooling
# r6i.2xlarge: 8 vCPU, 64 GB RAM

resource "aws_eks_node_group" "db_proxy" {
  cluster_name    = aws_eks_cluster.neopay_eks.name
  node_group_name = "db-proxy-nodes"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = aws_subnet.private_data[*].id
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = 3
    max_size     = 6
    min_size     = 2
  }

  instance_types = ["r6i.2xlarge"]

  launch_template {
    id      = aws_launch_template.db_proxy.id
    version = aws_launch_template.db_proxy.latest_version
  }

  labels = {
    "node-type" = "db-proxy"
    "workload-type" = "connection-pooling"
  }

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name = "neopay-${var.environment}-db-proxy-nodes"
  }
}

# =============================================================================
# Launch Templates
# =============================================================================

data "aws_ami" "eks_optimized" {
  filter {
    name   = "name"
    values = ["amazon-eks-node-*"]
  }
  most_recent = true
  owners      = ["602401143452"]  # AWS EKS
}

# System Node Launch Template
resource "aws_launch_template" "system" {
  name_prefix = "neopay-${var.environment}-system"
  
  image_id = data.aws_ami.eks_optimized.id

  vpc_security_group_ids = [aws_security_group.eks_nodes.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -o xtrace
    /etc/eks/bootstrap.sh neopay-${var.environment}-eks --kubelet-extra-args '--node-labels=node-type=system'
    /opt/aws/bin/cfn-signal --exit-code $? --stack ${aws_stack.neopay.arn} --resource system-nodes --region ${var.aws_region}
    EOF
  )

  iam_instance_profile {
    name = aws_iam_instance_profile.eks_nodes.name
  }

  monitoring {
    enabled = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 100
      volume_type = "gp3"
      encrypted   = true
      kms_key_id  = aws_kms_key.eks_nodes.arn
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "neopay-${var.environment}-system-node"
      NodeType = "system"
    }
  }
}

# Processing Node Launch Template
resource "aws_launch_template" "processing" {
  name_prefix = "neopay-${var.environment}-processing"
  
  image_id = data.aws_ami.eks_optimized.id

  vpc_security_group_ids = [aws_security_group.eks_nodes.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -o xtrace
    /etc/eks/bootstrap.sh neopay-${var.environment}-eks --kubelet-extra-args '--node-labels=node-type=processing --node-labels=workload-type=message-engine'
    /opt/aws/bin/cfn-signal --exit-code $? --stack ${aws_stack.neopay.arn} --resource processing-nodes --region ${var.aws_region}
    EOF
  )

  iam_instance_profile {
    name = aws_iam_instance_profile.eks_nodes.name
  }

  monitoring {
    enabled = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 200
      volume_type = "gp3"
      encrypted   = true
      kms_key_id  = aws_kms_key.eks_nodes.arn
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "neopay-${var.environment}-processing-node"
      NodeType = "processing"
    }
  }
}

# HSM Node Launch Template
resource "aws_launch_template" "hsm" {
  name_prefix = "neopay-${var.environment}-hsm"
  
  image_id = data.aws_ami.eks_optimized.id

  vpc_security_group_ids = [aws_security_group.eks_nodes.id, aws_security_group.cloudhsm.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -o xtrace
    /etc/eks/bootstrap.sh neopay-${var.environment}-eks --kubelet-extra-args '--node-labels=node-type=hsm --node-labels=workload-type=cryptographic'
    /opt/aws/bin/cfn-signal --exit-code $? --stack ${aws_stack.neopay.arn} --resource hsm-nodes --region ${var.aws_region}
    EOF
  )

  iam_instance_profile {
    name = aws_iam_instance_profile.eks_nodes.name
  }

  monitoring {
    enabled = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 100
      volume_type = "gp3"
      encrypted   = true
      kms_key_id  = aws_kms_key.eks_nodes.arn
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "neopay-${var.environment}-hsm-node"
      NodeType = "hsm"
    }
  }
}

# DB Proxy Launch Template
resource "aws_launch_template" "db_proxy" {
  name_prefix = "neopay-${var.environment}-db-proxy"
  
  image_id = data.aws_ami.eks_optimized.id

  vpc_security_group_ids = [aws_security_group.eks_nodes.id, aws_security_group.rds.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -o xtrace
    /etc/eks/bootstrap.sh neopay-${var.environment}-eks --kubelet-extra-args '--node-labels=node-type=db-proxy'
    /opt/aws/bin/cfn-signal --exit-code $? --stack ${aws_stack.neopay.arn} --resource db-proxy-nodes --region ${var.aws_region}
    EOF
  )

  iam_instance_profile {
    name = aws_iam_instance_profile.eks_nodes.name
  }

  monitoring {
    enabled = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 50
      volume_type = "gp3"
      encrypted   = true
      kms_key_id  = aws_kms_key.eks_nodes.arn
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "neopay-${var.environment}-db-proxy-node"
      NodeType = "db-proxy"
    }
  }
}

resource "aws_kms_key" "eks_nodes" {
  description = "KMS key for EKS node volumes"
  key_usage   = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_iam_instance_profile" "eks_nodes" {
  name = "neopay-${var.environment}-eks-nodes-ip"
  role = aws_iam_role.eks_node_role.name

  path = "/"
}

resource "aws_cloudformation_stack" "neopay" {
  name = "neopay-${var.environment}"

  template_body = <<-EOF
   AWSTemplateFormatVersion: '2010-09-09'
    Description: Neopay EKS Node Group Stack
    Resources:
      system-nodes:
        Type: AWS::AutoScaling::LaunchConfiguration
        Properties:
          LaunchConfigurationName: neopay-system-lc
      processing-nodes:
        Type: AWS::AutoScaling::LaunchConfiguration
        Properties:
          LaunchConfigurationName: neopay-processing-lc
      hsm-nodes:
        Type: AWS::AutoScaling::LaunchConfiguration
        Properties:
          LaunchConfigurationName: neopay-hsm-lc
      db-proxy-nodes:
        Type: AWS::AutoScaling::LaunchConfiguration
        Properties:
          LaunchConfigurationName: neopay-db-proxy-lc
    EOF
}

# =============================================================================
# Karpenter Provisioner (Optional: Auto-scaling)
# =============================================================================

resource "aws_karpenter_provisioner" "default" {
  name = "default"

  requirements {
    key       = "node.kubernetes.io/instance-type"
    operator  = "In"
    values    = ["m6i.xlarge", "m6i.2xlarge", "m6i.4xlarge", "r6i.xlarge", "r6i.2xlarge", "c6i.xlarge", "c6i.2xlarge"]
  }

  requirements {
    key       = "kubernetes.io/arch"
    operator  = "In"
    values    = ["amd64"]
  }

  requirements {
    key       = "topology.kubernetes.io/zone"
    operator  = "In"
    values    = var.availability_zones
  }

  weight = 100

  limits {
    resources = {
      cpu    = "100"
      memory = "400Gi"
    }
  }

  provider {
    instanceProfile = aws_iam_instance_profile.eks_nodes.name
    securityGroupIds = [aws_security_group.eks_nodes.id]
    subnetTags = {
      "Name" = "neopay-${var.environment}-private-app-*"
    }
  }

  ttl_seconds_after_empty = 300
}
