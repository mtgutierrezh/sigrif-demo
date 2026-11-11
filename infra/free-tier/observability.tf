resource "aws_cloudwatch_log_group" "api" {
  name              = "/${var.project}/${var.environment}/api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "ia" {
  name              = "/${var.project}/${var.environment}/ia"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "nginx" {
  name              = "/${var.project}/${var.environment}/nginx"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "db" {
  name              = "/${var.project}/${var.environment}/db"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/${var.project}/${var.environment}/ingest"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  count = var.alert_email != "" ? 1 : 0

  name = "${var.project}-${var.environment}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

locals {
  alarm_actions = var.alert_email != "" ? [aws_sns_topic.alerts[0].arn] : []
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project}-${var.environment}-cpu-high"
  alarm_description   = "CPU sostenida sobre 70% en el servidor SIGRIF"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 70
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.app.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "status_check" {
  alarm_name          = "${var.project}-${var.environment}-status-check"
  alarm_description   = "Chequeo de estado de la instancia EC2 fallando"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.app.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

resource "aws_budgets_budget" "monthly" {
  count = var.budget_email != "" ? 1 : 0

  name         = "${var.project}-${var.environment}-monthly"
  budget_type  = "COST"
  limit_amount = var.budget_limit_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
