locals {
  required_services = toset([
    "calendar-json.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  oauth_secret_inputs = {
    GOOGLE_OAUTH_CLIENT_ID     = var.google_oauth_client_id
    GOOGLE_OAUTH_CLIENT_SECRET = var.google_oauth_client_secret
  }

  oauth_secret_versions = var.create_secret_versions ? {
    for secret_name, secret_value in local.oauth_secret_inputs :
    secret_name => secret_value
    if secret_value != null && trimspace(secret_value) != ""
  } : {}
}

resource "terraform_data" "validate_bootstrap_inputs" {
  lifecycle {
    precondition {
      condition = (
        var.create_secret_versions == false ||
        length(local.oauth_secret_versions) == length(local.oauth_secret_inputs)
      )
      error_message = "When create_secret_versions=true, both google_oauth_client_id and google_oauth_client_secret are required."
    }
  }
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "oauth" {
  for_each = local.oauth_secret_inputs

  project   = var.project_id
  secret_id = each.key

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.required["secretmanager.googleapis.com"],
  ]
}

resource "google_secret_manager_secret_version" "oauth_bootstrap" {
  for_each = local.oauth_secret_versions

  secret      = google_secret_manager_secret.oauth[each.key].id
  secret_data = each.value

  depends_on = [
    terraform_data.validate_bootstrap_inputs,
  ]
}

resource "google_secret_manager_secret_iam_member" "backend_secret_accessor" {
  for_each = (
    var.backend_service_account_email == null ||
    trimspace(var.backend_service_account_email) == ""
  ) ? {} : google_secret_manager_secret.oauth

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${trimspace(var.backend_service_account_email)}"
}
