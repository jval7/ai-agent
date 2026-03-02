variable "project_id" {
  description = "Google Cloud project ID where APIs and secrets will be managed."
  type        = string

  validation {
    condition     = trimspace(var.project_id) != ""
    error_message = "project_id is required."
  }
}

variable "region" {
  description = "Default GCP region for provider configuration."
  type        = string
  default     = "us-central1"
}

variable "backend_service_account_email" {
  description = "Optional backend service account email that needs Secret Manager access."
  type        = string
  default     = null
  nullable    = true
}

variable "create_secret_versions" {
  description = "If true, Terraform creates secret versions from google_oauth_client_id and google_oauth_client_secret values."
  type        = bool
  default     = false
}

variable "google_oauth_client_id" {
  description = "Manual OAuth client ID from Google Cloud Console. Optional unless create_secret_versions=true."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

variable "google_oauth_client_secret" {
  description = "Manual OAuth client secret from Google Cloud Console. Optional unless create_secret_versions=true."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

variable "google_oauth_redirect_uri" {
  description = "OAuth redirect URI configured in Google OAuth client."
  type        = string
  default     = "http://localhost:8000/oauth/google/callback"
}
