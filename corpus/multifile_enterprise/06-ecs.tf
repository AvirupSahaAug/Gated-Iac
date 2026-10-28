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
