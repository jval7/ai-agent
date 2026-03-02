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
    [for api in google_project_service.apis : api.service],
  )
}
