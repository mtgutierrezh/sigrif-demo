variable "project" {
  description = "Prefijo de los recursos del proyecto."
  type        = string
  default     = "sigrif"
}

variable "environment" {
  description = "Ambiente lógico del despliegue."
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "Región de AWS. us-east-2 mantiene baja la latencia desde Chile."
  type        = string
  default     = "us-east-2"
}

variable "instance_type" {
  description = "Tipo de instancia. t3.micro es la opción económica; t3.small solo si la memoria no alcanza."
  type        = string
  default     = "t3.micro"
}

variable "allowed_http_cidr" {
  description = "CIDR autorizado para HTTP. Se restringe a 0.0.0.0/0 porque el sitio es público."
  type        = string
  default     = "0.0.0.0/0"
}

variable "allowed_https_cidr" {
  description = "CIDR autorizado para HTTPS."
  type        = string
  default     = "0.0.0.0/0"
}

variable "duckdns_subdomain" {
  description = "Subdominio de DuckDNS, sin .duckdns.org. Si queda vacío se usa domain_name."
  type        = string
  default     = ""
}

variable "duckdns_token" {
  description = "Token de DuckDNS. Se guarda en SSM Parameter Store, no en el repositorio."
  type        = string
  default     = ""
  sensitive   = true
}

variable "domain_name" {
  description = "Dominio propio opcional. Si está vacío se intenta usar el subdominio DuckDNS."
  type        = string
  default     = ""
}

variable "letsencrypt_email" {
  description = "Correo para Certbot/Let's Encrypt. Sin correo no se emite certificado."
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Correo opcional para alertas de CloudWatch."
  type        = string
  default     = ""
}

variable "budget_email" {
  description = "Correo opcional para el presupuesto de AWS. Sin correo no se crea el presupuesto."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  description = "Límite mensual de aviso en USD."
  type        = string
  default     = "5"
}

variable "log_retention_days" {
  description = "Días de retención de logs en CloudWatch."
  type        = number
  default     = 7
}

variable "github_repository" {
  description = "Repositorio autorizado para asumir el rol de despliegue por OIDC."
  type        = string
  default     = "mtgutierrezh/sigrif-demo"
}

variable "ghcr_username" {
  description = "Usuario de GitHub para descargar imágenes privadas de GHCR. Opcional si los paquetes son públicos."
  type        = string
  default     = ""
}

variable "ghcr_token" {
  description = "Token de GitHub con read:packages para descargar imágenes privadas de GHCR."
  type        = string
  default     = ""
  sensitive   = true
}

variable "enable_github_oidc" {
  description = "Crear el proveedor OIDC y el rol de despliegue de GitHub. Algunas organizaciones bloquean iam:CreateOpenIDConnectProvider por SCP."
  type        = bool
  default     = false
}

variable "dmc_user" {
  description = "Usuario del servicio DMC para la red EMA."
  type        = string
  default     = ""
}

variable "dmc_token" {
  description = "Token del servicio DMC. Se guarda en SSM; nunca en el repositorio."
  type        = string
  default     = ""
  sensitive   = true
}
