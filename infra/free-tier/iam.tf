data "aws_iam_policy_document" "ec2_assume" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "app" {
  name               = "${var.project}-${var.environment}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "app" {
  statement {
    sid    = "ArtifactsBucket"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]
  }

  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.api.arn}:*",
      "${aws_cloudwatch_log_group.ia.arn}:*",
      "${aws_cloudwatch_log_group.nginx.arn}:*",
      "${aws_cloudwatch_log_group.db.arn}:*",
      "${aws_cloudwatch_log_group.ingest.arn}:*",
    ]
  }

  statement {
    sid    = "ReadBootstrapSecrets"
    effect = "Allow"

    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]

    resources = [
      aws_ssm_parameter.db_password.arn,
      aws_ssm_parameter.duckdns_token.arn,
      aws_ssm_parameter.ghcr_token.arn,
      aws_ssm_parameter.dmc_user.arn,
      aws_ssm_parameter.dmc_token.arn,
      aws_ssm_parameter.grafana_password.arn,
    ]
  }

  statement {
    sid    = "DecryptSsmParameters"
    effect = "Allow"

    actions   = ["kms:Decrypt"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }

  statement {
    sid    = "BedrockNovaLite"
    effect = "Allow"

    actions = ["bedrock:InvokeModel"]

    resources = [
      "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-lite-v1:0",
    ]
  }

  statement {
    sid    = "DataBus"
    effect = "Allow"

    actions = [
      "sns:Publish",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility",
    ]

    resources = [
      aws_sns_topic.data.arn,
      aws_sqs_queue.readings.arn,
      aws_sqs_queue.readings_dlq.arn,
    ]
  }

  dynamic "statement" {
    for_each = local.alert_topic_arn != "" ? [local.alert_topic_arn] : []

    content {
      sid       = "AlertPublish"
      effect    = "Allow"
      actions   = ["sns:Publish"]
      resources = [statement.value]
    }
  }
}

resource "aws_iam_role_policy" "app" {
  name   = "${var.project}-${var.environment}-app"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project}-${var.environment}-ec2"
  role = aws_iam_role.app.name
}
