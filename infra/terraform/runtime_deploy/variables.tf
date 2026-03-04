variable "project_id" {
  description = "GCP project ID where runtime resources are deployed."
  type        = string

  validation {
    condition     = trimspace(var.project_id) != ""
    error_message = "project_id is required."
  }
}

variable "region" {
  description = "Cloud Run region."
  type        = string
  default     = "us-central1"
}

variable "artifact_registry_location" {
  description = "Artifact Registry region. Must support Docker repositories."
  type        = string
  default     = "us-central1"
}

variable "artifact_repository_id" {
  description = "Artifact Registry repository ID."
  type        = string
  default     = "ai-agent-backend"
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name for backend API."
  type        = string
  default     = "ai-agent-backend"
}

variable "runtime_service_account_email" {
  description = "Cloud Run runtime service account email."
  type        = string

  validation {
    condition     = trimspace(var.runtime_service_account_email) != ""
    error_message = "runtime_service_account_email is required."
  }
}

variable "container_image" {
  description = "Full container image URL (including tag or digest) deployed to Cloud Run."
  type        = string

  validation {
    condition     = trimspace(var.container_image) != ""
    error_message = "container_image is required."
  }
}

variable "allow_unauthenticated" {
  description = "If true, allows public unauthenticated access to Cloud Run service."
  type        = bool
  default     = true
}

variable "min_instances" {
  description = "Minimum Cloud Run instances."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum Cloud Run instances."
  type        = number
  default     = 10
}

variable "container_concurrency" {
  description = "Max concurrent requests per instance."
  type        = number
  default     = 40
}

variable "timeout_seconds" {
  description = "Request timeout in seconds."
  type        = number
  default     = 300
}

variable "cpu" {
  description = "CPU allocated to each Cloud Run instance."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory allocated to each Cloud Run instance."
  type        = string
  default     = "512Mi"
}

variable "container_port" {
  description = "Container port exposed by the backend app."
  type        = number
  default     = 8000
}

variable "ingress" {
  description = "Cloud Run ingress setting."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"

  validation {
    condition = contains([
      "INGRESS_TRAFFIC_ALL",
      "INGRESS_TRAFFIC_INTERNAL_ONLY",
      "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER",
    ], var.ingress)
    error_message = "ingress must be one of Cloud Run accepted values."
  }
}

variable "manage_app_config_secret" {
  description = "If true, Terraform manages the single JSON app config secret container and bootstrap version."
  type        = bool
  default     = true
}

variable "app_config_secret_bootstrap_json" {
  description = "Bootstrap JSON content for app config secret (stored in tfstate). Keep it minimal and upsert sensitive values later."
  type        = string
  default     = "{}"
  sensitive   = true
}

variable "enable_apis" {
  description = "APIs required by runtime deployment."
  type        = set(string)
  default = [
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}
