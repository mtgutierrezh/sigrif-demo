terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.tags
  }
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Delivery    = "free-tier"
  }

  duckdns_fqdn = var.duckdns_subdomain != "" ? "${var.duckdns_subdomain}.duckdns.org" : ""
  fqdn         = var.domain_name != "" ? var.domain_name : local.duckdns_fqdn

  callback_urls = concat(
    ["http://localhost:8080/auth/callback"],
    local.fqdn != "" ? ["https://${local.fqdn}/auth/callback"] : [],
  )
  logout_urls = concat(
    ["http://localhost:8080/"],
    local.fqdn != "" ? ["https://${local.fqdn}/"] : [],
  )

  app_origin = local.fqdn != "" ? "https://${local.fqdn}" : ""
}
