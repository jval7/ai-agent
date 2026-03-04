output "project_id" {
  description = "Created project ID."
  value       = google_project.project.project_id
}

output "project_number" {
  description = "Created project number."
  value       = google_project.project.number
}

output "enabled_apis" {
  description = "APIs enabled in the project by this stack."
  value = concat(
    ["serviceusage.googleapis.com"],
    var.enable_firestore ? [google_project_service.firestore[0].service] : [],
    [for api in google_project_service.apis : api.service],
  )
}

output "firestore_database_name" {
  description = "Firestore database resource name when create_firestore_database=true."
  value       = var.create_firestore_database ? google_firestore_database.default[0].name : null
}

output "oauth_secret_ids" {
  description = "Secret IDs created for OAuth in Secret Manager."
  value = var.manage_oauth_secrets ? {
    for secret_name, secret in google_secret_manager_secret.oauth :
    secret_name => secret.secret_id
  } : {}
}

output "oauth_secret_resource_names" {
  description = "Full Secret Manager resource names created for OAuth secrets."
  value = var.manage_oauth_secrets ? {
    for secret_name, secret in google_secret_manager_secret.oauth :
    secret_name => secret.id
  } : {}
}

output "google_oauth_redirect_uri" {
  description = "Redirect URI that must match Google OAuth client configuration."
  value       = var.google_oauth_redirect_uri
}

output "oauth_secret_versions_bootstrapped" {
  description = "True when secret versions were created by Terraform."
  value       = var.manage_oauth_secrets && var.create_oauth_secret_versions
}
