output "aws_region" {
  value = var.aws_region
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "nginx_repository_url" {
  value = aws_ecr_repository.nginx.repository_url
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "ia_service_name" {
  value = aws_ecs_service.ia.name
}

output "nginx_service_name" {
  value = aws_ecs_service.nginx.name
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "sns_topic_arn" {
  value = aws_sns_topic.data.arn
}

output "sqs_queue_url" {
  value = aws_sqs_queue.readings.id
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = aws_cognito_user_pool_domain.main.domain
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}
