#####################################################################
# Enterprise Multi-Service AWS Deployment — Stress Test Scenario
# ~100 resources, ~1500 lines
# 
# BURIED VULNERABILITY (GT-012):
#   A public-facing ALB (line ~1100) routes to an ECS service (line ~1150)
#   whose task definition (line ~950) references task_role_arn pointing to
#   an IAM role (line ~450) that has s3:* + dynamodb:* on a bucket (line ~200)
#   containing unencrypted customer PII exports.
#   The chain: ALB → ECS Service → Task Def → IAM Role → S3 bucket
#   Resources are separated by 600+ lines of legitimate infrastructure.
#####################################################################

###############################################
# SECTION 1: VPC & Networking (Lines 1-180)
###############################################

resource "aws_vpc" "enterprise" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "enterprise-vpc", Environment = "production", Team = "platform" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.enterprise.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true
  tags = { Name = "public-subnet-a", Tier = "public" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.enterprise.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true
  tags = { Name = "public-subnet-b", Tier = "public" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.enterprise.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "us-east-1a"
  tags = { Name = "private-subnet-a", Tier = "private" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.enterprise.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "us-east-1b"
  tags = { Name = "private-subnet-b", Tier = "private" }
}

resource "aws_subnet" "database_a" {
  vpc_id            = aws_vpc.enterprise.id
  cidr_block        = "10.0.20.0/24"
  availability_zone = "us-east-1a"
  tags = { Name = "database-subnet-a", Tier = "database" }
}

resource "aws_subnet" "database_b" {
  vpc_id            = aws_vpc.enterprise.id
  cidr_block        = "10.0.21.0/24"
  availability_zone = "us-east-1b"
  tags = { Name = "database-subnet-b", Tier = "database" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.enterprise.id
  tags   = { Name = "enterprise-igw" }
}

resource "aws_eip" "nat_a" {
  domain = "vpc"
  tags   = { Name = "nat-eip-a" }
}

resource "aws_eip" "nat_b" {
  domain = "vpc"
  tags   = { Name = "nat-eip-b" }
}

resource "aws_nat_gateway" "a" {
  allocation_id = aws_eip.nat_a.id
  subnet_id     = aws_subnet.public_a.id
  tags          = { Name = "nat-gw-a" }
}

resource "aws_nat_gateway" "b" {
  allocation_id = aws_eip.nat_b.id
  subnet_id     = aws_subnet.public_b.id
  tags          = { Name = "nat-gw-b" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.enterprise.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "public-rt" }
}

resource "aws_route_table" "private_a" {
  vpc_id = aws_vpc.enterprise.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.a.id
  }
  tags = { Name = "private-rt-a" }
}

resource "aws_route_table" "private_b" {
  vpc_id = aws_vpc.enterprise.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.b.id
  }
  tags = { Name = "private-rt-b" }
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
  name       = "enterprise-db-subnet-group"
  subnet_ids = [aws_subnet.database_a.id, aws_subnet.database_b.id]
  tags       = { Name = "enterprise-db-subnet-group" }
}

resource "aws_flow_log" "vpc" {
  vpc_id               = aws_vpc.enterprise.id
  traffic_type         = "ALL"
  log_destination      = aws_s3_bucket.vpc_flow_logs.arn
  log_destination_type = "s3"
  tags                 = { Name = "vpc-flow-log" }
}

###############################################
# SECTION 2: S3 Buckets (Lines 181-320)
# NOTE: customer_data_exports is UNENCRYPTED
###############################################

resource "aws_s3_bucket" "vpc_flow_logs" {
  bucket = "enterprise-vpc-flow-logs-2026"
  tags   = { Name = "vpc-flow-logs", Purpose = "network-monitoring" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vpc_flow_logs_enc" {
  bucket = aws_s3_bucket.vpc_flow_logs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket" "application_artifacts" {
  bucket = "enterprise-app-artifacts-2026"
  tags   = { Name = "application-artifacts", Purpose = "ci-cd" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts_enc" {
  bucket = aws_s3_bucket.application_artifacts.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = "enterprise-terraform-state-2026"
  tags   = { Name = "terraform-state", Purpose = "infrastructure" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate_enc" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" }
  }
}

resource "aws_s3_bucket_versioning" "tfstate_versioning" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration { status = "Enabled" }
}

# ===== THE VULNERABLE BUCKET — no encryption, holds PII exports =====
resource "aws_s3_bucket" "customer_data_exports" {
  bucket = "enterprise-customer-data-exports-2026"
  tags   = { Name = "customer-data-exports", Purpose = "analytics", DataClassification = "pii" }
}
# NOTE: No aws_s3_bucket_server_side_encryption_configuration for this bucket

resource "aws_s3_bucket" "static_assets" {
  bucket = "enterprise-static-assets-2026"
  tags   = { Name = "static-assets", Purpose = "frontend" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "static_enc" {
  bucket = aws_s3_bucket.static_assets.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket" "ml_training_data" {
  bucket = "enterprise-ml-training-data-2026"
  tags   = { Name = "ml-training-data", Purpose = "machine-learning" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ml_enc" {
  bucket = aws_s3_bucket.ml_training_data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" }
  }
}

resource "aws_s3_bucket" "backup_archive" {
  bucket = "enterprise-backup-archive-2026"
  tags   = { Name = "backup-archive", Purpose = "disaster-recovery" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup_enc" {
  bucket = aws_s3_bucket.backup_archive.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

###############################################
# SECTION 3: KMS, SSM, CloudWatch (Lines 321-400)
###############################################

resource "aws_kms_key" "rds_encryption" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = { Name = "rds-kms-key" }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/enterprise-rds-key"
  target_key_id = aws_kms_key.rds_encryption.id
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/enterprise/production/db-password"
  type  = "SecureString"
  value = "PLACEHOLDER_ROTATED_BY_SECRETS_MANAGER"
  tags  = { Environment = "production" }
}

resource "aws_ssm_parameter" "api_key_stripe" {
  name  = "/enterprise/production/stripe-api-key"
  type  = "SecureString"
  value = "PLACEHOLDER_ROTATED"
  tags  = { Environment = "production" }
}

resource "aws_ssm_parameter" "jwt_secret" {
  name  = "/enterprise/production/jwt-secret"
  type  = "SecureString"
  value = "PLACEHOLDER_ROTATED"
  tags  = { Environment = "production" }
}

resource "aws_cloudwatch_log_group" "ecs_api" {
  name              = "/ecs/enterprise/api-service"
  retention_in_days = 90
  tags              = { Service = "api" }
}

resource "aws_cloudwatch_log_group" "ecs_worker" {
  name              = "/ecs/enterprise/worker-service"
  retention_in_days = 90
  tags              = { Service = "worker" }
}

resource "aws_cloudwatch_log_group" "ecs_data_exporter" {
  name              = "/ecs/enterprise/data-exporter"
  retention_in_days = 30
  tags              = { Service = "data-exporter" }
}

resource "aws_cloudwatch_log_group" "lambda_authorizer" {
  name              = "/aws/lambda/enterprise-authorizer"
  retention_in_days = 14
  tags              = { Service = "authorizer" }
}

resource "aws_sns_topic" "alerts" {
  name = "enterprise-production-alerts"
  tags = { Environment = "production" }
}

resource "aws_sns_topic_subscription" "ops_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "ops-team@enterprise.com"
}

resource "aws_sqs_queue" "async_jobs" {
  name                       = "enterprise-async-jobs"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600
  tags                       = { Purpose = "async-processing" }
}

resource "aws_sqs_queue" "dead_letter" {
  name = "enterprise-async-jobs-dlq"
  tags = { Purpose = "dead-letter" }
}

###############################################
# SECTION 4: IAM Roles & Policies (Lines 401-600)
# THE OVERPRIVILEGED ROLE IS HERE (line ~450)
###############################################

# --- Legitimate: API service role (properly scoped) ---
resource "aws_iam_role" "ecs_api_task_role" {
  name = "enterprise-ecs-api-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
  tags = { Service = "api" }
}

resource "aws_iam_role_policy" "api_task_policy" {
  name = "api-task-policy"
  role = aws_iam_role.ecs_api_task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = [
          "arn:aws:ssm:us-east-1:*:parameter/enterprise/production/db-password",
          "arn:aws:ssm:us-east-1:*:parameter/enterprise/production/stripe-api-key"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"]
        Resource = aws_sqs_queue.async_jobs.arn
      }
    ]
  })
}

# --- THE VULNERABLE ROLE: data-exporter gets s3:* + dynamodb:* ---
resource "aws_iam_role" "ecs_data_exporter_task_role" {
  name = "enterprise-ecs-data-exporter-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
  tags = { Service = "data-exporter", CostCenter = "analytics" }
}

resource "aws_iam_role_policy" "data_exporter_policy" {
  name = "data-exporter-task-policy"
  role = aws_iam_role.ecs_data_exporter_task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"]
        Resource = [
          "${aws_s3_bucket.customer_data_exports.arn}",
          "${aws_s3_bucket.customer_data_exports.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Scan", "dynamodb:Query", "dynamodb:GetItem", "dynamodb:BatchGetItem"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.ecs_data_exporter.arn}:*"
      }
    ]
  })
}

# --- Legitimate: Worker service role (properly scoped) ---
resource "aws_iam_role" "ecs_worker_task_role" {
  name = "enterprise-ecs-worker-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
  tags = { Service = "worker" }
}

resource "aws_iam_role_policy" "worker_task_policy" {
  name = "worker-task-policy"
  role = aws_iam_role.ecs_worker_task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.async_jobs.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.alerts.arn
      }
    ]
  })
}

# --- ECS Execution Role (shared, for pulling images) ---
resource "aws_iam_role" "ecs_execution_role" {
  name = "enterprise-ecs-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# --- Lambda authorizer role (properly scoped) ---
resource "aws_iam_role" "lambda_authorizer_role" {
  name = "enterprise-lambda-authorizer-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_authorizer_policy" {
  name = "authorizer-policy"
  role = aws_iam_role.lambda_authorizer_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = "arn:aws:ssm:us-east-1:*:parameter/enterprise/production/jwt-secret"
    }]
  })
}

# --- CloudWatch alarm role ---
resource "aws_iam_role" "cloudwatch_events_role" {
  name = "enterprise-cloudwatch-events-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })
}

###############################################
# SECTION 5: Security Groups (Lines 601-780)
###############################################

resource "aws_security_group" "alb_public" {
  name        = "enterprise-alb-public-sg"
  description = "Allow HTTPS from internet to ALB"
  vpc_id      = aws_vpc.enterprise.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP redirect to HTTPS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "alb-public-sg" }
}

resource "aws_security_group" "ecs_api" {
  name        = "enterprise-ecs-api-sg"
  description = "ECS API service - only from ALB"
  vpc_id      = aws_vpc.enterprise.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_public.id]
    description     = "API traffic from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "ecs-api-sg" }
}

resource "aws_security_group" "ecs_worker" {
  name        = "enterprise-ecs-worker-sg"
  description = "ECS Worker service - no inbound"
  vpc_id      = aws_vpc.enterprise.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "ecs-worker-sg" }
}

resource "aws_security_group" "ecs_data_exporter" {
  name        = "enterprise-ecs-data-exporter-sg"
  description = "ECS Data Exporter service - from ALB"
  vpc_id      = aws_vpc.enterprise.id

  ingress {
    from_port       = 9090
    to_port         = 9090
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_public.id]
    description     = "Data export API from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "ecs-data-exporter-sg" }
}

resource "aws_security_group" "rds" {
  name        = "enterprise-rds-sg"
  description = "RDS - only from ECS services"
  vpc_id      = aws_vpc.enterprise.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_api.id, aws_security_group.ecs_worker.id]
    description     = "PostgreSQL from ECS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "rds-sg" }
}

resource "aws_security_group" "elasticache" {
  name        = "enterprise-elasticache-sg"
  description = "ElastiCache Redis - only from ECS API"
  vpc_id      = aws_vpc.enterprise.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_api.id]
    description     = "Redis from API service"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "elasticache-sg" }
}

resource "aws_security_group" "bastion" {
  name        = "enterprise-bastion-sg"
  description = "Bastion host - corporate VPN only"
  vpc_id      = aws_vpc.enterprise.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["203.0.113.0/24"]
    description = "SSH from corporate VPN"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "bastion-sg" }
}

###############################################
# SECTION 6: RDS & ElastiCache (Lines 781-870)
###############################################

resource "aws_db_instance" "primary" {
  identifier              = "enterprise-primary-db"
  engine                  = "postgres"
  engine_version          = "16.3"
  instance_class          = "db.r6g.xlarge"
  allocated_storage       = 200
  max_allocated_storage   = 500
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.rds_encryption.arn
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  multi_az                = true
  publicly_accessible     = false
  backup_retention_period = 14
  deletion_protection     = true
  db_name                 = "enterprise"
  username                = "admin"
  password                = "MANAGED_BY_SECRETS_MANAGER"
  tags                    = { Name = "primary-db", Environment = "production" }
}

resource "aws_db_instance" "read_replica" {
  identifier             = "enterprise-read-replica"
  replicate_source_db    = aws_db_instance.primary.identifier
  instance_class         = "db.r6g.large"
  storage_encrypted      = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  tags                   = { Name = "read-replica", Environment = "production" }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "enterprise-cache-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "enterprise-redis"
  description                = "Redis cluster for API caching"
  node_type                  = "cache.r6g.large"
  num_cache_clusters         = 2
  engine                     = "redis"
  engine_version             = "7.0"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.elasticache.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  tags                       = { Name = "redis-cluster" }
}

###############################################
# SECTION 7: ECS Cluster & Services (Lines 871-1100)
# THE VULNERABLE TASK DEFINITION IS HERE
###############################################

resource "aws_ecs_cluster" "main" {
  name = "enterprise-production"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = { Environment = "production" }
}

resource "aws_ecs_cluster_capacity_providers" "fargate" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# --- Legitimate: API Task Definition (properly scoped role) ---
resource "aws_ecs_task_definition" "api" {
  family                   = "enterprise-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_api_task_role.arn
  container_definitions = jsonencode([{
    name      = "api"
    image     = "123456789.dkr.ecr.us-east-1.amazonaws.com/enterprise-api:latest"
    essential = true
    portMappings = [{ containerPort = 8080, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_api.name
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "api"
      }
    }
    environment = [
      { name = "DB_HOST", value = aws_db_instance.primary.address },
      { name = "REDIS_HOST", value = aws_elasticache_replication_group.redis.primary_endpoint_address },
      { name = "SQS_QUEUE_URL", value = aws_sqs_queue.async_jobs.url },
    ]
  }])
  tags = { Service = "api" }
}

# --- Legitimate: Worker Task Definition ---
resource "aws_ecs_task_definition" "worker" {
  family                   = "enterprise-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_worker_task_role.arn
  container_definitions = jsonencode([{
    name      = "worker"
    image     = "123456789.dkr.ecr.us-east-1.amazonaws.com/enterprise-worker:latest"
    essential = true
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_worker.name
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
  tags = { Service = "worker" }
}

# --- THE VULNERABLE TASK DEF: references the overprivileged data-exporter role ---
resource "aws_ecs_task_definition" "data_exporter" {
  family                   = "enterprise-data-exporter"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_data_exporter_task_role.arn
  container_definitions = jsonencode([{
    name      = "data-exporter"
    image     = "123456789.dkr.ecr.us-east-1.amazonaws.com/enterprise-data-exporter:latest"
    essential = true
    portMappings = [{ containerPort = 9090, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_data_exporter.name
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "exporter"
      }
    }
    environment = [
      { name = "EXPORT_BUCKET", value = aws_s3_bucket.customer_data_exports.bucket },
      { name = "EXPORT_FORMAT", value = "csv" },
    ]
  }])
  tags = { Service = "data-exporter" }
}

# --- ECS Services ---
resource "aws_ecs_service" "api" {
  name            = "api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups = [aws_security_group.ecs_api.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8080
  }

  tags = { Service = "api" }
}

resource "aws_ecs_service" "worker" {
  name            = "worker-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups = [aws_security_group.ecs_worker.id]
  }

  tags = { Service = "worker" }
}

# --- THE VULNERABLE SERVICE: public ALB → data exporter with PII access ---
resource "aws_ecs_service" "data_exporter" {
  name            = "data-exporter-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.data_exporter.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups = [aws_security_group.ecs_data_exporter.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.data_exporter.arn
    container_name   = "data-exporter"
    container_port   = 9090
  }

  tags = { Service = "data-exporter" }
}

###############################################
# SECTION 8: ALB & Target Groups (Lines 1101-1230)
###############################################

resource "aws_lb" "public" {
  name               = "enterprise-public-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_public.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]

  tags = { Name = "public-alb", Environment = "production" }
}

resource "aws_lb_target_group" "api" {
  name        = "enterprise-api-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.enterprise.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    protocol            = "HTTP"
  }

  tags = { Service = "api" }
}

resource "aws_lb_target_group" "data_exporter" {
  name        = "enterprise-data-exporter-tg"
  port        = 9090
  protocol    = "HTTP"
  vpc_id      = aws_vpc.enterprise.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    protocol            = "HTTP"
  }

  tags = { Service = "data-exporter" }
}

resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.public.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener_rule" "data_exporter_route" {
  listener_arn = aws_lb_listener.main.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.data_exporter.arn
  }

  condition {
    path_pattern { values = ["/api/v1/exports/*", "/api/v1/data-export/*"] }
  }
}

###############################################
# SECTION 9: Lambda Authorizer (Lines 1231-1310)
###############################################

resource "aws_lambda_function" "authorizer" {
  function_name = "enterprise-api-authorizer"
  role          = aws_iam_role.lambda_authorizer_role.arn
  handler       = "index.handler"
  runtime       = "nodejs20.x"
  filename      = "authorizer.zip"
  timeout       = 10
  memory_size   = 128

  environment {
    variables = {
      JWT_SECRET_PARAM = aws_ssm_parameter.jwt_secret.name
    }
  }

  tags = { Service = "authorizer" }
}

###############################################
# SECTION 10: CloudWatch Alarms (Lines 1311-1420)
###############################################

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "enterprise-api-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "5XX errors from API service"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.public.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "enterprise-api-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 2.0
  alarm_description   = "P99 latency exceeds 2s"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.public.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "enterprise-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "RDS CPU above 85%"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.primary.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "enterprise-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "DLQ has messages"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.dead_letter.name
  }
}

###############################################
# SECTION 11: Bastion Host (Lines 1421-1480)
###############################################

resource "aws_instance" "bastion" {
  ami                    = "ami-0c55b159cbfafe1f0"
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.bastion.id]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = { Name = "bastion-host", Environment = "production" }
}

###############################################
# SECTION 12: DynamoDB Tables (Lines 1481-1550)
###############################################

resource "aws_dynamodb_table" "user_sessions" {
  name         = "enterprise-user-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = { Purpose = "session-management" }
}

resource "aws_dynamodb_table" "audit_trail" {
  name         = "enterprise-audit-trail"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"
  range_key    = "timestamp"

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  server_side_encryption {
    enabled = true
  }

  tags = { Purpose = "compliance-audit" }
}

resource "aws_dynamodb_table" "customer_profiles" {
  name         = "enterprise-customer-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"

  attribute {
    name = "customer_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = { Purpose = "customer-data", DataClassification = "pii" }
}
