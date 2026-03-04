variable "project_id" {
  description = "GCP project ID where WIF and service accounts will be created."
  type        = string

  validation {
    condition     = trimspace(var.project_id) != ""
    error_message = "project_id is required."
  }
}

variable "github_repository" {
  description = "GitHub repository in format owner/repo allowed to use this WIF provider."
  type        = string

  validation {
    condition     = trimspace(var.github_repository) != ""
    error_message = "github_repository is required."
  }
}

variable "github_branch" {
  description = "Git branch allowed to impersonate the deployer service account."
  type        = string
  default     = "main"

  validation {
    condition     = trimspace(var.github_branch) != ""
    error_message = "github_branch cannot be empty."
  }
}

variable "wif_pool_id" {
  description = "Workload Identity Pool ID."
  type        = string
  default     = "github-actions-pool"
}

variable "wif_provider_id" {
  description = "Workload Identity Pool Provider ID."
  type        = string
  default     = "github-provider"
}

variable "deployer_service_account_id" {
  description = "Service account ID impersonated by GitHub Actions."
  type        = string
  default     = "github-actions-deployer"
}

variable "runtime_service_account_id" {
  description = "Runtime service account ID used by Cloud Run."
  type        = string
  default     = "ai-agent-runtime"
}

variable "deployer_project_roles" {
  description = "Base project roles granted to the deployer service account."
  type        = set(string)
  default = [
    "roles/artifactregistry.admin",
    "roles/run.admin",
    "roles/serviceusage.serviceUsageAdmin",
  ]
}

variable "additional_deployer_project_roles" {
  description = "Optional extra project roles for deployer service account."
  type        = set(string)
  default     = []
}
