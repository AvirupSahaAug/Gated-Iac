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
