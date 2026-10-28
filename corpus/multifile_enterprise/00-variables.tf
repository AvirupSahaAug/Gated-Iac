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
