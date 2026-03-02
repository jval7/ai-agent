output "enabled_services" {
  description = "Project services enabled by this Terraform stack."
  value       = [for service in google_project_service.required : service.service]
}

output "oauth_secret_ids" {
  description = "Secret IDs created in Secret Manager."
  value = {
    for secret_name, secret in google_secret_manager_secret.oauth :
    secret_name => secret.secret_id
  }
}

output "oauth_secret_resource_names" {
  description = "Full Secret Manager resource names created by this stack."
  value = {
    for secret_name, secret in google_secret_manager_secret.oauth :
    secret_name => secret.id
  }
}

output "google_oauth_redirect_uri" {
  description = "Redirect URI that must match Google OAuth client configuration."
  value       = var.google_oauth_redirect_uri
}

output "secret_versions_bootstrapped" {
  description = "True when secret versions were created by Terraform."
  value       = var.create_secret_versions
}
