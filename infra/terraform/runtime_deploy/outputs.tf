output "artifact_repository_id" {
  description = "Artifact Registry repository ID."
  value       = google_artifact_registry_repository.backend.repository_id
}

output "artifact_repository_location" {
  description = "Artifact Registry repository location."
  value       = google_artifact_registry_repository.backend.location
}

output "artifact_repository_docker_base" {
  description = "Base Docker registry path for pushed images."
  value       = "${google_artifact_registry_repository.backend.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}"
}

output "cloud_run_service_name" {
  description = "Cloud Run backend service name."
  value       = google_cloud_run_v2_service.backend.name
}

output "cloud_run_service_url" {
  description = "Cloud Run backend URL."
  value       = google_cloud_run_v2_service.backend.uri
}

output "runtime_service_account_email" {
  description = "Runtime service account email attached to Cloud Run."
  value       = var.runtime_service_account_email
}

output "app_config_secret_id" {
  description = "Secret Manager ID used for app runtime config."
  value       = local.app_config_secret_id
}
