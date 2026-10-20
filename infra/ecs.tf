resource "aws_ecs_cluster" "main" {
  name = var.project
}

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "sigrif.local"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "api" {
  name = "api"

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"

    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_service_discovery_service" "ia" {
  name = "ia"

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"

    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.image_tag}"
      essential = true
      command   = ["uvicorn", "sigrif.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "SNS_TOPIC_ARN", value = aws_sns_topic.data.arn },
        { name = "SQS_QUEUE_URL", value = aws_sqs_queue.readings.url },
        { name = "AUTH_ENABLED", value = "true" },
        { name = "COGNITO_REGION", value = var.aws_region },
        { name = "COGNITO_USER_POOL_ID", value = aws_cognito_user_pool.main.id },
        { name = "COGNITO_CLIENT_ID", value = aws_cognito_user_pool_client.web.id },
        { name = "LOG_LEVEL", value = "INFO" }
      ]

      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 40
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "ia" {
  family                   = "${var.project}-ia"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "ia"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.image_tag}"
      essential = true
      command   = ["uvicorn", "sigrif.ia.main:app", "--host", "0.0.0.0", "--port", "8001"]

      portMappings = [
        {
          containerPort = 8001
          hostPort      = 8001
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "SNS_TOPIC_ARN", value = aws_sns_topic.data.arn },
        { name = "SQS_QUEUE_URL", value = aws_sqs_queue.readings.url },
        { name = "LOG_LEVEL", value = "INFO" }
      ]

      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health')\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 40
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ia.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ia"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "nginx" {
  family                   = "${var.project}-nginx"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "nginx"
      image     = "${aws_ecr_repository.nginx.repository_url}:${var.image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "API_HOST", value = "api.sigrif.local:8000" }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nginx.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "nginx"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name             = "api"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.api.arn
  desired_count    = var.desired_count
  launch_type      = "FARGATE"
  platform_version = "LATEST"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.api.arn
  }

  depends_on = [aws_iam_role_policy_attachment.execution]
}

resource "aws_ecs_service" "ia" {
  name             = "ia"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.ia.arn
  desired_count    = var.desired_count
  launch_type      = "FARGATE"
  platform_version = "LATEST"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ia.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.ia.arn
  }

  depends_on = [aws_iam_role_policy_attachment.execution]
}

resource "aws_ecs_service" "nginx" {
  name             = "nginx"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.nginx.arn
  desired_count    = var.desired_count
  launch_type      = "FARGATE"
  platform_version = "LATEST"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.nginx.id]
    assign_public_ip = true
  }

  depends_on = [aws_ecs_service.api, aws_iam_role_policy_attachment.execution]
}
