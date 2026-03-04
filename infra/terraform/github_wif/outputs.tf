output "deployer_service_account_email" {
  description = "Service account email to use in GitHub Actions auth step."
  value       = google_service_account.deployer.email
}

output "runtime_service_account_email" {
  description = "Runtime service account email for Cloud Run service."
  value       = google_service_account.runtime.email
}

output "workload_identity_provider_name" {
  description = "Fully qualified Workload Identity Provider resource name."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "workload_identity_pool_name" {
  description = "Fully qualified Workload Identity Pool resource name."
  value       = google_iam_workload_identity_pool.github.name
}

output "github_repository" {
  description = "Repository allowed by this provider."
  value       = var.github_repository
}

output "github_branch" {
  description = "Branch allowed by this provider."
  value       = var.github_branch
}
