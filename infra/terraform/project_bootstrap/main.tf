locals {
  org_id_normalized    = var.org_id == null ? "" : trimspace(var.org_id)
  folder_id_normalized = var.folder_id == null ? "" : trimspace(var.folder_id)

  custom_enabled_apis = toset([
    for api in var.enable_apis : trimspace(api)
    if trimspace(api) != "" && trimspace(api) != "serviceusage.googleapis.com"
  ])
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

resource "google_project_service" "apis" {
  for_each = local.custom_enabled_apis

  project            = google_project.project.project_id
  service            = each.key
  disable_on_destroy = false

  depends_on = [
    google_project_service.serviceusage,
  ]
}
