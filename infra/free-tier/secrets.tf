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
