output "app_url" {
  description = "URL pública esperada del sistema."
  value       = local.fqdn != "" ? "https://${local.fqdn}" : "http://${aws_eip.app.public_ip}"
}

output "public_ip" {
  description = "IP pública estable de la instancia; DuckDNS la actualiza cada cinco minutos."
  value       = aws_eip.app.public_ip
}

output "instance_id" {
  description = "ID de la instancia para SSM."
  value       = aws_instance.app.id
}

output "artifact_bucket" {
  description = "Bucket S3 para dataset, modelo y bundles de despliegue."
  value       = aws_s3_bucket.artifacts.bucket
}

output "cognito_user_pool_id" {
  description = "User pool de Cognito."
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Client ID público del frontend."
  value       = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  description = "Dominio hosted UI de Cognito."
  value       = aws_cognito_user_pool_domain.main.domain
}

output "github_deploy_role_arn" {
  description = "Rol que asume GitHub Actions por OIDC, si enable_github_oidc está activo."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy[0].arn : null
}

output "ssm_session_command" {
  description = "Comando para abrir sesión sin SSH."
  value       = "aws ssm start-session --target ${aws_instance.app.id}"
}

output "logs" {
  description = "Nombres de los grupos de logs."
  value = {
    api   = aws_cloudwatch_log_group.api.name
    ia    = aws_cloudwatch_log_group.ia.name
    nginx = aws_cloudwatch_log_group.nginx.name
    db    = aws_cloudwatch_log_group.db.name
  }
}

output "data_topic_arn" {
  description = "Topic SNS de lecturas meteorológicas."
  value       = aws_sns_topic.data.arn
}

output "data_queue_url" {
  description = "Cola SQS consumida por el servicio de IA."
  value       = aws_sqs_queue.readings.id
}

output "grafana_admin_password" {
  description = "Clave inicial del administrador de Grafana."
  value       = random_password.grafana.result
  sensitive   = true
}
