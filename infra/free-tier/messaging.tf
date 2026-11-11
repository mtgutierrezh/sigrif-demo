resource "aws_sns_topic" "data" {
  name = "${var.project}-${var.environment}-datos"
}

resource "aws_sqs_queue" "readings_dlq" {
  name                      = "${var.project}-${var.environment}-lecturas-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "readings" {
  name                       = "${var.project}-${var.environment}-lecturas"
  visibility_timeout_seconds = 120
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.readings_dlq.arn
    maxReceiveCount     = 3
  })
}

data "aws_iam_policy_document" "readings_queue" {
  statement {
    sid    = "AllowSigrifDataTopic"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.readings.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.data.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "readings" {
  queue_url = aws_sqs_queue.readings.id
  policy    = data.aws_iam_policy_document.readings_queue.json
}

resource "aws_sns_topic_subscription" "readings" {
  topic_arn = aws_sns_topic.data.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.readings.arn
}

locals {
  alert_topic_arn = var.alert_email != "" ? aws_sns_topic.alerts[0].arn : ""
}
