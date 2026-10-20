resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_cognito_user_pool" "main" {
  name                     = "${var.project}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project}-${random_id.suffix.hex}"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.project}-web"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
  callback_urls = [
    "http://localhost:5173/auth/callback",
    "http://localhost:8080/auth/callback",
  ]
  logout_urls = [
    "http://localhost:5173/",
    "http://localhost:8080/",
  ]
}

resource "aws_cognito_user_group" "users" {
  name         = "usuarios"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Consulta de mapa, riesgo y reportes"
}

resource "aws_cognito_user_group" "operators" {
  name         = "operadores"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Fuentes, reentrenamiento, umbrales y alertas"
}
