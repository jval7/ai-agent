variable "project_id" {
  description = "GCP project ID where frontend CDN resources are deployed."
  type        = string

  validation {
    condition     = trimspace(var.project_id) != ""
    error_message = "project_id is required."
  }
}

variable "frontend_domains" {
  description = "Custom domains served by HTTPS load balancer certificate (for example: [\"app.example.com\"])."
  type        = list(string)
  default     = []

  validation {
    condition = (
      alltrue([for domain in var.frontend_domains : trimspace(domain) != ""])
    )
    error_message = "frontend_domains cannot include empty values."
  }
}

variable "bucket_name" {
  description = "Optional Cloud Storage bucket name for SPA assets. If null, defaults to <project_id>-frontend-spa."
  type        = string
  default     = null
  nullable    = true
}

variable "bucket_location" {
  description = "Cloud Storage bucket location or multi-region."
  type        = string
  default     = "US"

  validation {
    condition     = trimspace(var.bucket_location) != ""
    error_message = "bucket_location is required."
  }
}

variable "resource_name_prefix" {
  description = "Prefix used to name load balancer resources."
  type        = string
  default     = "ai-agent-frontend"

  validation {
    condition     = trimspace(var.resource_name_prefix) != ""
    error_message = "resource_name_prefix is required."
  }
}

variable "enable_cdn" {
  description = "If true, enables Cloud CDN on the backend bucket."
  type        = bool
  default     = true
}

variable "enable_https" {
  description = "If true, creates managed certificate and HTTPS listener. Requires at least one frontend_domains value."
  type        = bool
  default     = true
}

variable "enable_http_redirect" {
  description = "If true, HTTP (80) redirects to HTTPS (443)."
  type        = bool
  default     = true
}

variable "force_destroy_bucket" {
  description = "If true, allows destroying non-empty bucket (useful only for ephemeral environments)."
  type        = bool
  default     = false
}

variable "index_document" {
  description = "Main page for SPA website hosting."
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Error page for SPA fallback. Use index.html for client-side routing."
  type        = string
  default     = "index.html"
}

variable "enable_apis" {
  description = "APIs required for frontend CDN deployment."
  type        = set(string)
  default = [
    "compute.googleapis.com",
    "storage.googleapis.com",
  ]
}
