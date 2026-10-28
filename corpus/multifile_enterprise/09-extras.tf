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
