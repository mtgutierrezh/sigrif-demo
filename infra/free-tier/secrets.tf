resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_ssm_parameter" "db_password" {
  name        = "/${var.project}/${var.environment}/db_password"
  description = "Clave de PostgreSQL/PostGIS para SIGRIF"
  type        = "SecureString"
  value       = random_password.db.result

  tags = {
    Name = "${var.project}-${var.environment}-db-password"
  }
}

resource "aws_ssm_parameter" "duckdns_token" {
  name        = "/${var.project}/${var.environment}/duckdns_token"
  description = "Token de DuckDNS para actualizar la IP pública"
  type        = "SecureString"
  value       = var.duckdns_token != "" ? var.duckdns_token : "unused"

  tags = {
    Name = "${var.project}-${var.environment}-duckdns-token"
  }
}

resource "aws_ssm_parameter" "ghcr_token" {
  name        = "/${var.project}/${var.environment}/ghcr_token"
  description = "Token de GitHub para descargar imágenes privadas de GHCR"
  type        = "SecureString"
  value       = var.ghcr_token != "" ? var.ghcr_token : "unused"

  tags = {
    Name = "${var.project}-${var.environment}-ghcr-token"
  }
}

resource "aws_ssm_parameter" "dmc_user" {
  name        = "/${var.project}/${var.environment}/dmc_user"
  description = "Usuario del servicio DMC para la ingesta meteorologica"
  type        = "SecureString"
  value       = var.dmc_user != "" ? var.dmc_user : "unused"

  tags = {
    Name = "${var.project}-${var.environment}-dmc-user"
  }
}

resource "aws_ssm_parameter" "dmc_token" {
  name        = "/${var.project}/${var.environment}/dmc_token"
  description = "Token del servicio DMC para la ingesta meteorologica"
  type        = "SecureString"
  value       = var.dmc_token != "" ? var.dmc_token : "unused"

  tags = {
    Name = "${var.project}-${var.environment}-dmc-token"
  }
}

resource "random_password" "grafana" {
  length  = 24
  special = false
}

resource "aws_ssm_parameter" "grafana_password" {
  name        = "/${var.project}/${var.environment}/grafana_password"
  description = "Clave inicial del administrador de Grafana"
  type        = "SecureString"
  value       = random_password.grafana.result

  tags = {
    Name = "${var.project}-${var.environment}-grafana-password"
  }
}
