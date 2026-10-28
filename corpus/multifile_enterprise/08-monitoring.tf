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
