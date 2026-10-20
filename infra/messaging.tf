resource "aws_sns_topic" "data" {
  name = "${var.project}-datos"
}

resource "aws_sqs_queue" "readings_dlq" {
  name                      = "${var.project}-lecturas-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "readings" {
  name                       = "${var.project}-lecturas"
  visibility_timeout_seconds = 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.readings_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue_policy" "readings" {
  queue_url = aws_sqs_queue.readings.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.readings.arn
        Condition = {
          ArnEquals = { "aws:SourceArn" = aws_sns_topic.data.arn }
        }
      }
    ]
  })
}

resource "aws_sns_topic_subscription" "readings" {
  topic_arn = aws_sns_topic.data.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.readings.arn
}
