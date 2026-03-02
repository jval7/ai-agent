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
  description = "Project APIs to enable after project creation."
  type        = set(string)
  default = [
    "calendar-json.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}
