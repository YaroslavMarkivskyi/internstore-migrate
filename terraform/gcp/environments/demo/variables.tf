variable "project_id" {
  description = "GCP project ID to provision into"
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "name_prefix" {
  type    = string
  default = "internstore-demo"
}

variable "internal_token_secret" {
  description = "Shared INTERNAL_TOKEN_SECRET (HMAC secret validated by every domain service). Generate a real value per demo session, don't reuse the local dev-only one."
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
  default   = "" # empty crash-loops ai-assistant/mcp-gateway on purpose, matching base's own placeholder behavior — set a real key before apply
}

variable "stripe_secret_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "stripe_webhook_secret" {
  type      = string
  sensitive = true
  default   = ""
}

variable "keycloak_client_secret" {
  type      = string
  sensitive = true
  default   = "dev-only-keycloak-client-secret-change-me"
}

variable "keycloak_admin_password" {
  type      = string
  sensitive = true
  default   = "admin"
}
