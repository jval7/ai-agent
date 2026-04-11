locals {
  app_config_secret_id = "AI_AGENT_APP_CONFIG_JSON"

  normalized_enable_apis = toset([
    for api in var.enable_apis : trimspace(api)
    if trimspace(api) != ""
  ])

  runtime_secret_ids = toset(var.manage_app_config_secret ? [local.app_config_secret_id] : [])
}

resource "google_project_service" "serviceusage" {
  project            = var.project_id
  service            = "serviceusage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "apis" {
  for_each = local.normalized_enable_apis

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false

  depends_on = [
    google_project_service.serviceusage,
  ]
}

resource "google_artifact_registry_repository" "backend" {
  project       = var.project_id
  location      = var.artifact_registry_location
  repository_id = var.artifact_repository_id
  description   = "Docker repository for AI Agent backend"
  format        = "DOCKER"

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_secret_manager_secret" "app_config_json" {
  count = var.manage_app_config_secret ? 1 : 0

  project   = var.project_id
  secret_id = local.app_config_secret_id

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_cloud_run_v2_service" "backend" {
  project  = var.project_id
  location = var.region
  name     = var.cloud_run_service_name
  ingress  = var.ingress

  template {
    service_account                  = var.runtime_service_account_email
    timeout                          = "${var.timeout_seconds}s"
    max_instance_request_concurrency = var.container_concurrency

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      ports {
        container_port = var.container_port
      }

    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_secret_manager_secret_iam_member" "runtime_secret_accessor" {
  for_each = local.runtime_secret_ids

  project   = var.project_id
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.runtime_service_account_email}"
}

# ── Cloud Tasks queue for auto-close booked sessions ─────────────────

resource "google_cloud_tasks_queue" "auto_close_booked" {
  project  = var.project_id
  location = var.region
  name     = var.cloud_tasks_queue_name

  rate_limits {
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 5
  }

  retry_config {
    max_attempts       = 5
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_retry_duration = "3600s"
  }

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_cloud_tasks_queue_iam_member" "runtime_enqueuer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_tasks_queue.auto_close_booked.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${var.runtime_service_account_email}"
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
