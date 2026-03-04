output "frontend_bucket_name" {
  description = "Cloud Storage bucket that stores SPA assets."
  value       = google_storage_bucket.frontend_assets.name
}

output "frontend_load_balancer_ip" {
  description = "Global IP address for the frontend HTTPS load balancer."
  value       = google_compute_global_address.frontend_spa.address
}

output "frontend_domains" {
  description = "Domains configured in the managed SSL certificate."
  value       = var.frontend_domains
}

output "frontend_https_url" {
  description = "Primary frontend HTTPS URL (null when HTTPS is disabled)."
  value       = length(var.frontend_domains) > 0 && var.enable_https ? "https://${var.frontend_domains[0]}" : null
}

output "frontend_http_url" {
  description = "Frontend HTTP URL (useful for local/quick iteration when HTTPS is disabled)."
  value       = "http://${google_compute_global_address.frontend_spa.address}"
}

output "frontend_upload_command" {
  description = "Command to upload frontend build output to the bucket."
  value       = "gcloud storage rsync --recursive ./frontend/dist gs://${google_storage_bucket.frontend_assets.name}"
}
