variable "project_id" {
  description = "Unique GCP project ID to create."
  type        = string

  validation {
    condition     = trimspace(var.project_id) != ""
    error_message = "project_id is required."
  }
}

variable "project_name" {
  description = "Human-readable GCP project name."
  type        = string

  validation {
    condition     = trimspace(var.project_name) != ""
    error_message = "project_name is required."
  }
}

variable "billing_account_id" {
  description = "Billing account ID in format XXXX-XXXXXX-XXXXXX."
  type        = string

  validation {
    condition     = trimspace(var.billing_account_id) != ""
    error_message = "billing_account_id is required."
  }
}

variable "org_id" {
  description = "Optional organization ID. Use only if project must live under an organization."
  type        = string
  default     = null
  nullable    = true
}

variable "folder_id" {
  description = "Optional folder ID. Use only if project must live under a folder."
  type        = string
  default     = null
  nullable    = true
}

variable "labels" {
  description = "Optional labels for the project."
  type        = map(string)
  default     = {}
}

variable "enable_apis" {
  description = "Project APIs to enable after project creation. Include secretmanager.googleapis.com when manage_oauth_secrets=true."
  type        = set(string)
  default = [
    "calendar-json.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}

variable "enable_firestore" {
  description = "Enable Firestore API in the created project."
  type        = bool
  default     = true
}

variable "create_firestore_database" {
  description = "Create Firestore default database in Native mode."
  type        = bool
  default     = true
}

variable "firestore_location_id" {
  description = "Firestore database location ID (for example: nam5, us-central1, southamerica-east1)."
  type        = string
  default     = "nam5"

  validation {
    condition     = trimspace(var.firestore_location_id) != ""
    error_message = "firestore_location_id is required when create_firestore_database=true."
  }
}

variable "manage_oauth_secrets" {
  description = "If true, create Secret Manager containers for GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
  type        = bool
  default     = true
}

variable "create_oauth_secret_versions" {
  description = "If true, Terraform creates secret versions from google_oauth_client_id and google_oauth_client_secret values."
  type        = bool
  default     = false
}

variable "google_oauth_client_id" {
  description = "Manual OAuth client ID from Google Cloud Console. Optional unless create_oauth_secret_versions=true."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

variable "google_oauth_client_secret" {
  description = "Manual OAuth client secret from Google Cloud Console. Optional unless create_oauth_secret_versions=true."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

variable "google_oauth_redirect_uri" {
  description = "OAuth redirect URI configured in Google OAuth client."
  type        = string
  default     = "http://localhost:8000/oauth/google/callback"

  validation {
    condition     = trimspace(var.google_oauth_redirect_uri) != ""
    error_message = "google_oauth_redirect_uri cannot be empty."
  }
}

variable "backend_service_account_email" {
  description = "Optional backend service account email that needs Secret Manager access (Cloud Run runtime SA)."
  type        = string
  default     = null
  nullable    = true
}
