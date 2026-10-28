#!/usr/bin/env python3
"""Generate a multi-file Terraform enterprise structure for stress testing.
Vulnerability chain spans 4 files:
  07-alb.tf (public ALB) → 06-ecs.tf (data-exporter service) → 
  03-iam.tf (overprivileged role) → 05-s3.tf (unencrypted PII bucket)
"""
import os

OUT = "corpus/multifile_enterprise"

files = {}

# ─────────── FILE 0: variables.tf (~80 lines) ───────────
files["00-variables.tf"] = '''
variable "region" { default = "us-east-1" }
variable "environment" { default = "production" }
variable "project" { default = "enterprise-platform" }
variable "vpc_cidr" { default = "10.0.0.0/16" }
variable "public_subnet_cidrs" { default = ["10.0.1.0/24", "10.0.2.0/24"] }
variable "private_subnet_cidrs" { default = ["10.0.10.0/24", "10.0.11.0/24"] }
variable "database_subnet_cidrs" { default = ["10.0.20.0/24", "10.0.21.0/24"] }
variable "db_instance_class" { default = "db.r6g.xlarge" }
variable "db_allocated_storage" { default = 200 }
variable "db_engine_version" { default = "16.3" }
variable "ecs_api_cpu" { default = "512" }
variable "ecs_api_memory" { default = "1024" }
variable "ecs_worker_cpu" { default = "256" }
variable "ecs_worker_memory" { default = "512" }
variable "ecs_exporter_cpu" { default = "1024" }
variable "ecs_exporter_memory" { default = "2048" }
variable "redis_node_type" { default = "cache.r6g.large" }
variable "redis_num_replicas" { default = 2 }
variable "api_desired_count" { default = 3 }
variable "worker_desired_count" { default = 2 }
variable "exporter_desired_count" { default = 1 }
variable "api_max_count" { default = 20 }
variable "api_min_count" { default = 3 }
variable "alert_email" { default = "ops-team@enterprise.com" }
variable "corporate_vpn_cidr" { default = "203.0.113.0/24" }
variable "certificate_arn" { default = "arn:aws:acm:us-east-1:123456789:certificate/prod" }
variable "ecr_registry" { default = "123456789.dkr.ecr.us-east-1.amazonaws.com" }
variable "api_image_tag" { default = "v2.4.1" }
variable "worker_image_tag" { default = "v1.8.0" }
variable "exporter_image_tag" { default = "v3.1.0" }
variable "lambda_authorizer_zip" { default = "authorizer.zip" }
variable "bastion_ami" { default = "ami-0c55b159cbfafe1f0" }
variable "enable_waf" { default = true }
variable "backup_retention_days" { default = 14 }
variable "log_retention_days" { default = 90 }
variable "enable_deletion_protection" { default = true }

locals {
  common_tags = {
    Environment = var.environment
    Project     = var.project
    ManagedBy   = "terraform"
  }
  az_a = "${var.region}a"
  az_b = "${var.region}b"
}
'''.strip()

# ─────────── FILE 1: vpc.tf (~350 lines of networking boilerplate) ───────────
files["01-vpc.tf"] = '''
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = merge(local.common_tags, { Name = "${var.project}-vpc" })
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[0]
  availability_zone       = local.az_a
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, { Name = "public-a", Tier = "public" })
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[1]
  availability_zone       = local.az_b
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, { Name = "public-b", Tier = "public" })
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[0]
  availability_zone = local.az_a
  tags = merge(local.common_tags, { Name = "private-a", Tier = "private" })
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[1]
  availability_zone = local.az_b
  tags = merge(local.common_tags, { Name = "private-b", Tier = "private" })
}

resource "aws_subnet" "database_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.database_subnet_cidrs[0]
  availability_zone = local.az_a
  tags = merge(local.common_tags, { Name = "database-a", Tier = "database" })
}

resource "aws_subnet" "database_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.database_subnet_cidrs[1]
  availability_zone = local.az_b
  tags = merge(local.common_tags, { Name = "database-b", Tier = "database" })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.common_tags, { Name = "${var.project}-igw" })
}

resource "aws_eip" "nat_a" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "nat-eip-a" })
}

resource "aws_eip" "nat_b" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "nat-eip-b" })
}

resource "aws_nat_gateway" "a" {
  allocation_id = aws_eip.nat_a.id
  subnet_id     = aws_subnet.public_a.id
  tags          = merge(local.common_tags, { Name = "nat-gw-a" })
}

resource "aws_nat_gateway" "b" {
  allocation_id = aws_eip.nat_b.id
  subnet_id     = aws_subnet.public_b.id
  tags          = merge(local.common_tags, { Name = "nat-gw-b" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; gateway_id = aws_internet_gateway.main.id }
  tags = merge(local.common_tags, { Name = "public-rt" })
}

resource "aws_route_table" "private_a" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; nat_gateway_id = aws_nat_gateway.a.id }
  tags = merge(local.common_tags, { Name = "private-rt-a" })
}

resource "aws_route_table" "private_b" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; nat_gateway_id = aws_nat_gateway.b.id }
  tags = merge(local.common_tags, { Name = "private-rt-b" })
}

resource "aws_route_table_association" "pub_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "pub_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "priv_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private_a.id
}
resource "aws_route_table_association" "priv_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private_b.id
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-subnet-group"
  subnet_ids = [aws_subnet.database_a.id, aws_subnet.database_b.id]
  tags       = merge(local.common_tags, { Name = "db-subnet-group" })
}

resource "aws_flow_log" "vpc" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination      = aws_s3_bucket.flow_logs.arn
  log_destination_type = "s3"
  tags                 = merge(local.common_tags, { Name = "vpc-flow-log" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.region}.s3"
  route_table_ids = [aws_route_table.private_a.id, aws_route_table.private_b.id]
  tags = merge(local.common_tags, { Name = "s3-endpoint" })
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.region}.dynamodb"
  route_table_ids = [aws_route_table.private_a.id, aws_route_table.private_b.id]
  tags = merge(local.common_tags, { Name = "dynamodb-endpoint" })
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "ecr-api-endpoint" })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "ecr-dkr-endpoint" })
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "logs-endpoint" })
}

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "ssm-endpoint" })
}
'''.strip()

# ─────────── FILE 2: security-groups.tf (~250 lines) ───────────
files["02-security-groups.tf"] = '''
resource "aws_security_group" "alb_public" {
  name        = "${var.project}-alb-public-sg"
  description = "Allow HTTPS from internet to ALB"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 443; to_port = 443; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"]; description = "HTTPS" }
  ingress { from_port = 80; to_port = 80; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"]; description = "HTTP redirect" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "alb-public-sg" })
}

resource "aws_security_group" "ecs_api" {
  name        = "${var.project}-ecs-api-sg"
  description = "ECS API - from ALB only"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 8080; to_port = 8080; protocol = "tcp"; security_groups = [aws_security_group.alb_public.id]; description = "API from ALB" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "ecs-api-sg" })
}

resource "aws_security_group" "ecs_worker" {
  name        = "${var.project}-ecs-worker-sg"
  description = "ECS Worker - no inbound"
  vpc_id      = aws_vpc.main.id
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "ecs-worker-sg" })
}

resource "aws_security_group" "ecs_exporter" {
  name        = "${var.project}-ecs-exporter-sg"
  description = "ECS Data Exporter - from ALB"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 9090; to_port = 9090; protocol = "tcp"; security_groups = [aws_security_group.alb_public.id]; description = "Exporter from ALB" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "ecs-exporter-sg" })
}

resource "aws_security_group" "rds" {
  name        = "${var.project}-rds-sg"
  description = "RDS - from ECS only"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 5432; to_port = 5432; protocol = "tcp"; security_groups = [aws_security_group.ecs_api.id, aws_security_group.ecs_worker.id]; description = "PostgreSQL" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "rds-sg" })
}

resource "aws_security_group" "elasticache" {
  name        = "${var.project}-elasticache-sg"
  description = "ElastiCache - from API only"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 6379; to_port = 6379; protocol = "tcp"; security_groups = [aws_security_group.ecs_api.id]; description = "Redis" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "elasticache-sg" })
}

resource "aws_security_group" "bastion" {
  name        = "${var.project}-bastion-sg"
  description = "Bastion - corporate VPN only"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 22; to_port = 22; protocol = "tcp"; cidr_blocks = [var.corporate_vpn_cidr]; description = "SSH from VPN" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "bastion-sg" })
}

resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project}-vpc-endpoints-sg"
  description = "VPC Endpoints - from private subnets"
  vpc_id      = aws_vpc.main.id
  ingress { from_port = 443; to_port = 443; protocol = "tcp"; cidr_blocks = var.private_subnet_cidrs; description = "HTTPS from private" }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "vpc-endpoints-sg" })
}

resource "aws_security_group" "lambda" {
  name        = "${var.project}-lambda-sg"
  description = "Lambda functions"
  vpc_id      = aws_vpc.main.id
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = merge(local.common_tags, { Name = "lambda-sg" })
}
'''.strip()

# ─────────── FILE 3: iam.tf (~300 lines, VULNERABLE ROLE BURIED HERE) ───────────
files["03-iam.tf"] = '''
# ======== ECS Execution Role (shared) ========
resource "aws_iam_role" "ecs_execution" {
  name = "${var.project}-ecs-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = merge(local.common_tags, { Purpose = "ecs-execution" })
}
resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ======== API Service Task Role (properly scoped) ========
resource "aws_iam_role" "api_task" {
  name = "${var.project}-api-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = merge(local.common_tags, { Service = "api" })
}
resource "aws_iam_role_policy" "api_task" {
  name = "api-task-policy"
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["ssm:GetParameter", "ssm:GetParameters"]; Resource = ["arn:aws:ssm:${var.region}:*:parameter/${var.project}/production/*"] },
      { Effect = "Allow"; Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"]; Resource = aws_sqs_queue.async_jobs.arn }
    ]
  })
}

# ======== Worker Task Role (properly scoped) ========
resource "aws_iam_role" "worker_task" {
  name = "${var.project}-worker-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = merge(local.common_tags, { Service = "worker" })
}
resource "aws_iam_role_policy" "worker_task" {
  name = "worker-task-policy"
  role = aws_iam_role.worker_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]; Resource = aws_sqs_queue.async_jobs.arn },
      { Effect = "Allow"; Action = ["sns:Publish"]; Resource = aws_sns_topic.alerts.arn }
    ]
  })
}

# ======== THE OVERPRIVILEGED ROLE — data-exporter ========
resource "aws_iam_role" "exporter_task" {
  name = "${var.project}-data-exporter-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = merge(local.common_tags, { Service = "data-exporter", CostCenter = "analytics" })
}
resource "aws_iam_role_policy" "exporter_task" {
  name = "data-exporter-task-policy"
  role = aws_iam_role.exporter_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"]; Resource = ["${aws_s3_bucket.customer_exports.arn}", "${aws_s3_bucket.customer_exports.arn}/*"] },
      { Effect = "Allow"; Action = ["dynamodb:Scan", "dynamodb:Query", "dynamodb:GetItem", "dynamodb:BatchGetItem"]; Resource = "*" },
      { Effect = "Allow"; Action = ["logs:CreateLogStream", "logs:PutLogEvents"]; Resource = "${aws_cloudwatch_log_group.exporter.arn}:*" }
    ]
  })
}

# ======== Lambda Authorizer Role ========
resource "aws_iam_role" "lambda_authorizer" {
  name = "${var.project}-lambda-authorizer-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "lambda.amazonaws.com" } }]
  })
  tags = merge(local.common_tags, { Service = "authorizer" })
}
resource "aws_iam_role_policy" "lambda_authorizer" {
  name = "authorizer-policy"
  role = aws_iam_role.lambda_authorizer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow"; Action = ["ssm:GetParameter"]; Resource = "arn:aws:ssm:${var.region}:*:parameter/${var.project}/production/jwt-secret" }]
  })
}

# ======== CloudWatch Events Role ========
resource "aws_iam_role" "cw_events" {
  name = "${var.project}-cw-events-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "events.amazonaws.com" } }]
  })
  tags = local.common_tags
}

# ======== Backup Role ========
resource "aws_iam_role" "backup" {
  name = "${var.project}-backup-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "backup.amazonaws.com" } }]
  })
  tags = local.common_tags
}
resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}
'''.strip()

# ─────────── FILE 4: rds.tf ───────────
files["04-rds.tf"] = '''
resource "aws_kms_key" "rds" {
  description             = "KMS for RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags = merge(local.common_tags, { Purpose = "rds-encryption" })
}
resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project}-rds-key"
  target_key_id = aws_kms_key.rds.id
}
resource "aws_db_instance" "primary" {
  identifier              = "${var.project}-primary"
  engine                  = "postgres"
  engine_version          = var.db_engine_version
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  max_allocated_storage   = 500
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.rds.arn
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  multi_az                = true
  publicly_accessible     = false
  backup_retention_period = var.backup_retention_days
  deletion_protection     = var.enable_deletion_protection
  db_name                 = "enterprise"
  username                = "admin"
  password                = "MANAGED_BY_SECRETS_MANAGER"
  tags = merge(local.common_tags, { Name = "primary-db" })
}
resource "aws_db_instance" "read_replica" {
  identifier             = "${var.project}-read-replica"
  replicate_source_db    = aws_db_instance.primary.identifier
  instance_class         = "db.r6g.large"
  storage_encrypted      = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  tags = merge(local.common_tags, { Name = "read-replica" })
}
'''.strip()

# ─────────── FILE 5: s3.tf (UNENCRYPTED PII BUCKET HERE) ───────────
files["05-s3.tf"] = '''
resource "aws_s3_bucket" "flow_logs" {
  bucket = "${var.project}-flow-logs"
  tags = merge(local.common_tags, { Purpose = "network-monitoring" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "flow_logs" {
  bucket = aws_s3_bucket.flow_logs.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project}-artifacts"
  tags = merge(local.common_tags, { Purpose = "ci-cd" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket" "tfstate" {
  bucket = "${var.project}-tfstate"
  tags = merge(local.common_tags, { Purpose = "infrastructure" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" } }
}
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration { status = "Enabled" }
}

# ===== THE VULNERABLE BUCKET — PII exports, NO encryption =====
resource "aws_s3_bucket" "customer_exports" {
  bucket = "${var.project}-customer-data-exports"
  tags = merge(local.common_tags, { Purpose = "analytics", DataClassification = "pii" })
}
# NOTE: No encryption configuration for this bucket!

resource "aws_s3_bucket" "static_assets" {
  bucket = "${var.project}-static-assets"
  tags = merge(local.common_tags, { Purpose = "frontend" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket" "ml_training" {
  bucket = "${var.project}-ml-training"
  tags = merge(local.common_tags, { Purpose = "machine-learning" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "ml_training" {
  bucket = aws_s3_bucket.ml_training.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" } }
}

resource "aws_s3_bucket" "backup_archive" {
  bucket = "${var.project}-backup-archive"
  tags = merge(local.common_tags, { Purpose = "disaster-recovery" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "backup_archive" {
  bucket = aws_s3_bucket.backup_archive.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}
'''.strip()

# ─────────── FILE 6: ecs.tf (VULNERABLE TASK DEF) ───────────
files["06-ecs.tf"] = '''
resource "aws_ecs_cluster" "main" {
  name = var.project
  setting { name = "containerInsights"; value = "enabled" }
  tags = local.common_tags
}
resource "aws_ecs_cluster_capacity_providers" "fargate" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy { capacity_provider = "FARGATE"; weight = 1 }
}

# ======== API Task Definition (properly scoped) ========
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_api_cpu
  memory                   = var.ecs_api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.api_task.arn
  container_definitions = jsonencode([{
    name = "api"; image = "${var.ecr_registry}/${var.project}-api:${var.api_image_tag}"; essential = true
    portMappings = [{ containerPort = 8080; protocol = "tcp" }]
    logConfiguration = { logDriver = "awslogs"; options = { "awslogs-group" = aws_cloudwatch_log_group.api.name; "awslogs-region" = var.region; "awslogs-stream-prefix" = "api" } }
    environment = [{ name = "DB_HOST"; value = aws_db_instance.primary.address }, { name = "REDIS_HOST"; value = aws_elasticache_replication_group.redis.primary_endpoint_address }]
  }])
  tags = merge(local.common_tags, { Service = "api" })
}

# ======== Worker Task Definition (properly scoped) ========
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_worker_cpu
  memory                   = var.ecs_worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn
  container_definitions = jsonencode([{
    name = "worker"; image = "${var.ecr_registry}/${var.project}-worker:${var.worker_image_tag}"; essential = true
    logConfiguration = { logDriver = "awslogs"; options = { "awslogs-group" = aws_cloudwatch_log_group.worker.name; "awslogs-region" = var.region; "awslogs-stream-prefix" = "worker" } }
  }])
  tags = merge(local.common_tags, { Service = "worker" })
}

# ======== THE VULNERABLE TASK DEF — references the overprivileged exporter role ========
resource "aws_ecs_task_definition" "exporter" {
  family                   = "${var.project}-data-exporter"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_exporter_cpu
  memory                   = var.ecs_exporter_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.exporter_task.arn
  container_definitions = jsonencode([{
    name = "data-exporter"; image = "${var.ecr_registry}/${var.project}-data-exporter:${var.exporter_image_tag}"; essential = true
    portMappings = [{ containerPort = 9090; protocol = "tcp" }]
    logConfiguration = { logDriver = "awslogs"; options = { "awslogs-group" = aws_cloudwatch_log_group.exporter.name; "awslogs-region" = var.region; "awslogs-stream-prefix" = "exporter" } }
    environment = [{ name = "EXPORT_BUCKET"; value = aws_s3_bucket.customer_exports.bucket }, { name = "EXPORT_FORMAT"; value = "csv" }]
  }])
  tags = merge(local.common_tags, { Service = "data-exporter" })
}

# ======== ECS Services ========
resource "aws_ecs_service" "api" {
  name            = "api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"
  network_configuration { subnets = [aws_subnet.private_a.id, aws_subnet.private_b.id]; security_groups = [aws_security_group.ecs_api.id] }
  load_balancer { target_group_arn = aws_lb_target_group.api.arn; container_name = "api"; container_port = 8080 }
  tags = merge(local.common_tags, { Service = "api" })
}

resource "aws_ecs_service" "worker" {
  name            = "worker-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"
  network_configuration { subnets = [aws_subnet.private_a.id, aws_subnet.private_b.id]; security_groups = [aws_security_group.ecs_worker.id] }
  tags = merge(local.common_tags, { Service = "worker" })
}

# ======== THE VULNERABLE SERVICE — public ALB routes to data-exporter ========
resource "aws_ecs_service" "exporter" {
  name            = "data-exporter-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.exporter.arn
  desired_count   = var.exporter_desired_count
  launch_type     = "FARGATE"
  network_configuration { subnets = [aws_subnet.private_a.id, aws_subnet.private_b.id]; security_groups = [aws_security_group.ecs_exporter.id] }
  load_balancer { target_group_arn = aws_lb_target_group.exporter.arn; container_name = "data-exporter"; container_port = 9090 }
  tags = merge(local.common_tags, { Service = "data-exporter" })
}
'''.strip()

# ─────────── FILE 7: alb.tf (PUBLIC ENTRY POINT) ───────────
files["07-alb.tf"] = '''
resource "aws_lb" "public" {
  name               = "${var.project}-public-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_public.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  tags = merge(local.common_tags, { Name = "public-alb" })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.project}-api-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check { path = "/health"; healthy_threshold = 3; unhealthy_threshold = 3; timeout = 5; interval = 30 }
  tags = merge(local.common_tags, { Service = "api" })
}

resource "aws_lb_target_group" "exporter" {
  name        = "${var.project}-exporter-tg"
  port        = 9090
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check { path = "/health"; healthy_threshold = 2; unhealthy_threshold = 3; timeout = 10; interval = 30 }
  tags = merge(local.common_tags, { Service = "data-exporter" })
}

resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.public.arn
  port              = 80
  protocol          = "HTTP"
  default_action { type = "forward"; target_group_arn = aws_lb_target_group.api.arn }
}

resource "aws_lb_listener_rule" "exporter_route" {
  listener_arn = aws_lb_listener.main.arn
  priority     = 100
  action { type = "forward"; target_group_arn = aws_lb_target_group.exporter.arn }
  condition { path_pattern { values = ["/api/v1/exports/*", "/api/v1/data-export/*"] } }
}
'''.strip()

# ─────────── FILE 8: monitoring.tf ───────────
files["08-monitoring.tf"] = '''
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project}/api"
  retention_in_days = var.log_retention_days
  tags = merge(local.common_tags, { Service = "api" })
}
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project}/worker"
  retention_in_days = var.log_retention_days
  tags = merge(local.common_tags, { Service = "worker" })
}
resource "aws_cloudwatch_log_group" "exporter" {
  name              = "/ecs/${var.project}/data-exporter"
  retention_in_days = 30
  tags = merge(local.common_tags, { Service = "data-exporter" })
}
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project}-authorizer"
  retention_in_days = 14
  tags = merge(local.common_tags, { Service = "authorizer" })
}

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
  tags = local.common_tags
}
resource "aws_sns_topic_subscription" "ops_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sqs_queue" "async_jobs" {
  name                       = "${var.project}-async-jobs"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600
  tags = merge(local.common_tags, { Purpose = "async-processing" })
}
resource "aws_sqs_queue" "dlq" {
  name = "${var.project}-dlq"
  tags = merge(local.common_tags, { Purpose = "dead-letter" })
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.project}-api-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { LoadBalancer = aws_lb.public.arn_suffix; TargetGroup = aws_lb_target_group.api.arn_suffix }
}
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.project}-rds-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { DBInstanceIdentifier = aws_db_instance.primary.identifier }
}
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.project}-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
}
'''.strip()

# ─────────── FILE 9: extras.tf (lambda, bastion, elasticache, dynamo) ───────────
files["09-extras.tf"] = '''
resource "aws_ssm_parameter" "db_password" {
  name  = "/${var.project}/production/db-password"
  type  = "SecureString"
  value = "PLACEHOLDER_ROTATED"
  tags  = local.common_tags
}
resource "aws_ssm_parameter" "jwt_secret" {
  name  = "/${var.project}/production/jwt-secret"
  type  = "SecureString"
  value = "PLACEHOLDER_ROTATED"
  tags  = local.common_tags
}

resource "aws_lambda_function" "authorizer" {
  function_name = "${var.project}-authorizer"
  role          = aws_iam_role.lambda_authorizer.arn
  handler       = "index.handler"
  runtime       = "nodejs20.x"
  filename      = var.lambda_authorizer_zip
  timeout       = 10
  memory_size   = 128
  environment { variables = { JWT_SECRET_PARAM = aws_ssm_parameter.jwt_secret.name } }
  tags = merge(local.common_tags, { Service = "authorizer" })
}

resource "aws_instance" "bastion" {
  ami                    = var.bastion_ami
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.bastion.id]
  metadata_options { http_endpoint = "enabled"; http_tokens = "required"; http_put_response_hop_limit = 1 }
  tags = merge(local.common_tags, { Name = "bastion" })
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project}-cache-subnets"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.project}-redis"
  description                = "Redis cluster for API caching"
  node_type                  = var.redis_node_type
  num_cache_clusters         = var.redis_num_replicas
  engine                     = "redis"
  engine_version             = "7.0"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.elasticache.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  tags = merge(local.common_tags, { Name = "redis-cluster" })
}

resource "aws_dynamodb_table" "sessions" {
  name = "${var.project}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "session_id"
  attribute { name = "session_id"; type = "S" }
  server_side_encryption { enabled = true }
  ttl { attribute_name = "expires_at"; enabled = true }
  tags = merge(local.common_tags, { Purpose = "session-management" })
}
resource "aws_dynamodb_table" "audit_trail" {
  name = "${var.project}-audit-trail"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "event_id"
  range_key = "timestamp"
  attribute { name = "event_id"; type = "S" }
  attribute { name = "timestamp"; type = "N" }
  server_side_encryption { enabled = true }
  tags = merge(local.common_tags, { Purpose = "compliance" })
}
resource "aws_dynamodb_table" "customer_profiles" {
  name = "${var.project}-customer-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "customer_id"
  attribute { name = "customer_id"; type = "S" }
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = true }
  tags = merge(local.common_tags, { Purpose = "customer-data", DataClassification = "pii" })
}

resource "aws_autoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = var.api_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
resource "aws_autoscaling_policy" "api_cpu" {
  name               = "${var.project}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_autoscaling_target.api.resource_id
  scalable_dimension = aws_autoscaling_target.api.scalable_dimension
  service_namespace  = aws_autoscaling_target.api.service_namespace
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
    target_value = 70.0
  }
}
'''.strip()

# Write all files
for fname, content in files.items():
    path = os.path.join(OUT, fname)
    with open(path, 'w') as f:
        f.write(content + '\n')
    lines = content.count('\n') + 1
    print(f"  {fname}: {lines} lines")

# Total
total_lines = sum(c.count('\n') + 1 for c in files.values())
total_chars = sum(len(c) for c in files.values())
print(f"\nTotal: {len(files)} files, {total_lines} lines, {total_chars} chars (~{total_chars//4} tokens)")

