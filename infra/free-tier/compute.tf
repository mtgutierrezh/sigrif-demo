data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = true
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region                 = var.aws_region
    db_name                    = "sigrif"
    db_user                    = "sigrif"
    db_password_parameter      = aws_ssm_parameter.db_password.name
    duckdns_token_parameter    = aws_ssm_parameter.duckdns_token.name
    duckdns_subdomain          = var.duckdns_subdomain
    fqdn                       = local.fqdn
    app_origin                 = local.app_origin
    cognito_region             = var.aws_region
    cognito_user_pool_id       = aws_cognito_user_pool.main.id
    cognito_client_id          = aws_cognito_user_pool_client.web.id
    s3_bucket                  = aws_s3_bucket.artifacts.bucket
    letsencrypt_email          = var.letsencrypt_email
    ghcr_username              = var.ghcr_username
    ghcr_token_parameter       = aws_ssm_parameter.ghcr_token.name
    dmc_user_parameter         = aws_ssm_parameter.dmc_user.name
    dmc_token_parameter        = aws_ssm_parameter.dmc_token.name
    grafana_password_parameter = aws_ssm_parameter.grafana_password.name
    data_topic_arn             = aws_sns_topic.data.arn
    data_queue_url             = aws_sqs_queue.readings.id
    alert_topic_arn            = local.alert_topic_arn
  })

  tags = {
    Name = "${var.project}-${var.environment}-app"
  }

  depends_on = [
    aws_iam_instance_profile.app,
    aws_iam_role_policy.app,
    aws_iam_role_policy_attachment.ssm_core,
    aws_ssm_parameter.db_password,
    aws_ssm_parameter.dmc_user,
    aws_ssm_parameter.dmc_token,
    aws_ssm_parameter.grafana_password,
    aws_sqs_queue_policy.readings,
    aws_sns_topic_subscription.readings,
  ]
}

resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = "${var.project}-${var.environment}-eip"
  }

  depends_on = [aws_instance.app]
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}
