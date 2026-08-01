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

variable "artifact_keep_recent_count" {
  description = "Number of most recent backend images kept regardless of age (rollback window)."
  type        = number
  default     = 5

  validation {
    condition     = var.artifact_keep_recent_count >= 1
    error_message = "artifact_keep_recent_count must be at least 1."
  }
}

variable "artifact_delete_older_than_days" {
  description = "Age in days after which backend images are deleted, unless kept by the recent-versions policy."
  type        = number
  default     = 30

  validation {
    condition     = var.artifact_delete_older_than_days >= 1
    error_message = "artifact_delete_older_than_days must be at least 1."
  }
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
  description = "Request timeout in seconds. SSE streams need this high (max 3600)."
  type        = number
  default     = 3600
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
  description = "If true, Terraform manages the single JSON app config secret container. Secret content is managed externally via gcloud or the settings API."
  type        = bool
  default     = true
}

variable "cloud_tasks_queue_name" {
  description = "Cloud Tasks queue name for scheduling tasks (reminders, auto-close)."
  type        = string
  default     = "scheduling-tasks"
}

variable "enable_apis" {
  description = "APIs required by runtime deployment."
  type        = set(string)
  default = [
    "artifactregistry.googleapis.com",
    "cloudtasks.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}
