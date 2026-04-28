locals {
  normalized_enable_apis = toset([
    for api in var.enable_apis : trimspace(api)
    if trimspace(api) != ""
  ])

  computed_bucket_name = (
    var.bucket_name == null
    ? "${var.project_id}-frontend-spa"
    : lower(trimspace(var.bucket_name))
  )

  resource_name_prefix_normalized = trimsuffix(
    substr(replace(lower(var.resource_name_prefix), "/[^a-z0-9-]/", "-"), 0, 40),
    "-"
  )

  https_enabled = var.enable_https && length(var.frontend_domains) > 0
}

resource "terraform_data" "validate_names" {
  lifecycle {
    precondition {
      condition     = can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", local.computed_bucket_name))
      error_message = "bucket_name must be a valid GCS bucket name (3-63 chars, lowercase, numbers, dot, underscore or dash)."
    }

    precondition {
      condition     = can(regex("^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$", local.resource_name_prefix_normalized))
      error_message = "resource_name_prefix must produce a valid GCP resource name."
    }

    precondition {
      condition     = var.enable_https == false || length(var.frontend_domains) > 0
      error_message = "When enable_https=true you must set at least one value in frontend_domains."
    }
  }
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

resource "google_storage_bucket" "frontend_assets" {
  project  = var.project_id
  name     = local.computed_bucket_name
  location = var.bucket_location

  uniform_bucket_level_access = true
  force_destroy               = var.force_destroy_bucket
  public_access_prevention    = "inherited"

  website {
    main_page_suffix = var.index_document
    not_found_page   = var.error_document
  }

  depends_on = [
    terraform_data.validate_names,
    google_project_service.apis,
  ]
}

resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.frontend_assets.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_compute_backend_bucket" "frontend_spa" {
  project     = var.project_id
  name        = "${local.resource_name_prefix_normalized}-backend-bucket"
  bucket_name = google_storage_bucket.frontend_assets.name
  enable_cdn  = var.enable_cdn

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_compute_global_address" "frontend_spa" {
  project    = var.project_id
  name       = "${local.resource_name_prefix_normalized}-ip"
  ip_version = "IPV4"

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_compute_managed_ssl_certificate" "frontend_spa" {
  count = local.https_enabled ? 1 : 0

  project = var.project_id
  name    = "${local.resource_name_prefix_normalized}-cert"

  managed {
    domains = var.frontend_domains
  }

  depends_on = [
    google_project_service.apis,
  ]
}

# TODO(rebrand-cleanup): cert temporal solo para agendachat.app durante la migración
# alejaescobar.com -> agendachat.app (2026-04-28).
# Razón: `domains` es ForceNew + nombre fijo del cert original = recreate causaría
# downtime de HTTPS hasta provisioning del cert nuevo (15min-24h).
# Cuando decommissionemos alejaescobar.com:
#   1. Cambiar var.frontend_domains a ["agendachat.app"] en envs/prod.tfvars
#   2. Borrar este recurso (frontend_spa_agendachat) y la entrada en ssl_certificates del https_proxy
#   3. terraform apply  -> recrea el cert original con solo agendachat.app y termina con un único cert
# Alternativa de largo plazo: refactorizar a random_id + lifecycle.create_before_destroy.
resource "google_compute_managed_ssl_certificate" "frontend_spa_agendachat" {
  count = local.https_enabled ? 1 : 0

  project = var.project_id
  name    = "${local.resource_name_prefix_normalized}-cert-agendachat"

  managed {
    domains = ["agendachat.app"]
  }

  depends_on = [
    google_project_service.apis,
  ]
}

resource "google_compute_url_map" "frontend_spa_https" {
  count = local.https_enabled ? 1 : 0

  project         = var.project_id
  name            = "${local.resource_name_prefix_normalized}-https-map"
  default_service = google_compute_backend_bucket.frontend_spa.id
}

resource "google_compute_target_https_proxy" "frontend_spa" {
  count = local.https_enabled ? 1 : 0

  project = var.project_id
  name    = "${local.resource_name_prefix_normalized}-https-proxy"
  url_map = google_compute_url_map.frontend_spa_https[0].id

  ssl_certificates = [
    google_compute_managed_ssl_certificate.frontend_spa[0].id,
    # TODO(rebrand-cleanup): remover esta entrada cuando se decommissione alejaescobar.com
    # (ver comentario sobre frontend_spa_agendachat arriba).
    google_compute_managed_ssl_certificate.frontend_spa_agendachat[0].id,
  ]
}

resource "google_compute_global_forwarding_rule" "frontend_spa_https" {
  count = local.https_enabled ? 1 : 0

  project    = var.project_id
  name       = "${local.resource_name_prefix_normalized}-https-fr"
  ip_address = google_compute_global_address.frontend_spa.address
  port_range = "443"
  target     = google_compute_target_https_proxy.frontend_spa[0].id
}

resource "google_compute_url_map" "frontend_spa_http_redirect" {
  count = local.https_enabled && var.enable_http_redirect ? 1 : 0

  project = var.project_id
  name    = "${local.resource_name_prefix_normalized}-http-redir-map"

  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
  }
}

resource "google_compute_target_http_proxy" "frontend_spa_http_redirect" {
  count = local.https_enabled && var.enable_http_redirect ? 1 : 0

  project = var.project_id
  name    = "${local.resource_name_prefix_normalized}-http-redir-proxy"
  url_map = google_compute_url_map.frontend_spa_http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "frontend_spa_http_redirect" {
  count = local.https_enabled && var.enable_http_redirect ? 1 : 0

  project    = var.project_id
  name       = "${local.resource_name_prefix_normalized}-http-redir-fr"
  ip_address = google_compute_global_address.frontend_spa.address
  port_range = "80"
  target     = google_compute_target_http_proxy.frontend_spa_http_redirect[0].id
}

resource "google_compute_url_map" "frontend_spa_http" {
  count = local.https_enabled ? 0 : 1

  project         = var.project_id
  name            = "${local.resource_name_prefix_normalized}-http-map"
  default_service = google_compute_backend_bucket.frontend_spa.id
}

resource "google_compute_target_http_proxy" "frontend_spa_http" {
  count = local.https_enabled ? 0 : 1

  project = var.project_id
  name    = "${local.resource_name_prefix_normalized}-http-proxy"
  url_map = google_compute_url_map.frontend_spa_http[0].id
}

resource "google_compute_global_forwarding_rule" "frontend_spa_http" {
  count = local.https_enabled ? 0 : 1

  project    = var.project_id
  name       = "${local.resource_name_prefix_normalized}-http-fr"
  ip_address = google_compute_global_address.frontend_spa.address
  port_range = "80"
  target     = google_compute_target_http_proxy.frontend_spa_http[0].id
}
