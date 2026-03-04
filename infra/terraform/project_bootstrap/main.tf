locals {
  org_id_normalized    = var.org_id == null ? "" : trimspace(var.org_id)
  folder_id_normalized = var.folder_id == null ? "" : trimspace(var.folder_id)

  normalized_enable_apis = toset([
    for api in var.enable_apis : trimspace(api)
    if trimspace(api) != ""
  ])

  custom_enabled_apis = toset([
    for api in local.normalized_enable_apis : api
    if api != "serviceusage.googleapis.com" && api != "firestore.googleapis.com"
  ])

  oauth_secret_inputs = {
    GOOGLE_OAUTH_CLIENT_ID     = var.google_oauth_client_id
    GOOGLE_OAUTH_CLIENT_SECRET = var.google_oauth_client_secret
  }

  oauth_secret_versions = (
    var.manage_oauth_secrets && var.create_oauth_secret_versions
    ? {
      for secret_name, secret_value in local.oauth_secret_inputs :
      secret_name => secret_value
      if secret_value != null && trimspace(secret_value) != ""
    }
    : {}
  )

  backend_service_account_email_normalized = (
    var.backend_service_account_email == null
    ? ""
    : trimspace(var.backend_service_account_email)
  )
}

resource "terraform_data" "validate_project_parent" {
  lifecycle {
    precondition {
      condition = !(
        local.org_id_normalized != "" &&
        local.folder_id_normalized != ""
      )
      error_message = "Set only one of org_id or folder_id."
    }
  }
}

resource "terraform_data" "validate_firestore_inputs" {
  lifecycle {
    precondition {
      condition     = var.create_firestore_database == false || var.enable_firestore == true
      error_message = "create_firestore_database=true requires enable_firestore=true."
    }
  }
}

resource "terraform_data" "validate_oauth_inputs" {
  lifecycle {
    precondition {
      condition = (
        var.manage_oauth_secrets == false ||
        contains(local.normalized_enable_apis, "secretmanager.googleapis.com")
      )
      error_message = "manage_oauth_secrets=true requires secretmanager.googleapis.com in enable_apis."
    }

    precondition {
      condition     = var.create_oauth_secret_versions == false || var.manage_oauth_secrets == true
      error_message = "create_oauth_secret_versions=true requires manage_oauth_secrets=true."
    }

    precondition {
      condition = (
        var.create_oauth_secret_versions == false ||
        length(local.oauth_secret_versions) == length(local.oauth_secret_inputs)
      )
      error_message = "When create_oauth_secret_versions=true, both google_oauth_client_id and google_oauth_client_secret are required."
    }
  }
}

resource "google_project" "project" {
  project_id      = var.project_id
  name            = var.project_name
  billing_account = var.billing_account_id
  labels          = var.labels

  org_id    = local.org_id_normalized == "" ? null : local.org_id_normalized
  folder_id = local.folder_id_normalized == "" ? null : local.folder_id_normalized

  depends_on = [
    terraform_data.validate_project_parent,
  ]
}

resource "google_project_service" "serviceusage" {
  project = google_project.project.project_id
  service = "serviceusage.googleapis.com"
}

resource "google_project_service" "firestore" {
  count = var.enable_firestore ? 1 : 0

  project            = google_project.project.project_id
  service            = "firestore.googleapis.com"
  disable_on_destroy = false

  depends_on = [
    google_project_service.serviceusage,
  ]
}

resource "google_project_service" "apis" {
  for_each = local.custom_enabled_apis

  project            = google_project.project.project_id
  service            = each.key
  disable_on_destroy = false

  depends_on = [
    google_project_service.serviceusage,
  ]
}

resource "google_firestore_database" "default" {
  count = var.create_firestore_database ? 1 : 0

  project     = google_project.project.project_id
  name        = "(default)"
  location_id = var.firestore_location_id
  type        = "FIRESTORE_NATIVE"

  depends_on = [
    terraform_data.validate_firestore_inputs,
    google_project_service.firestore,
  ]
}

resource "google_secret_manager_secret" "oauth" {
  for_each = var.manage_oauth_secrets ? local.oauth_secret_inputs : {}

  project   = google_project.project.project_id
  secret_id = each.key

  replication {
    auto {}
  }

  depends_on = [
    terraform_data.validate_oauth_inputs,
    google_project_service.apis,
  ]
}

resource "google_secret_manager_secret_version" "oauth_bootstrap" {
  for_each = local.oauth_secret_versions

  secret      = google_secret_manager_secret.oauth[each.key].id
  secret_data = each.value

  depends_on = [
    terraform_data.validate_oauth_inputs,
  ]
}

resource "google_secret_manager_secret_iam_member" "backend_secret_accessor" {
  for_each = local.backend_service_account_email_normalized == "" ? {} : google_secret_manager_secret.oauth

  project   = google_project.project.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.backend_service_account_email_normalized}"
}
