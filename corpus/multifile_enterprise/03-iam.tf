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
