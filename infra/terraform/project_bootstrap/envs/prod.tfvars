project_id         = "ai-agent-calendar-2603011621"
project_name       = "AI Agent Calendar Prod"
billing_account_id = "01E8FF-24B127-856018"

org_id    = null
folder_id = null

labels = {
  env   = "prod"
  owner = "jhon"
}

enable_apis = [
  "aiplatform.googleapis.com",
  "calendar-json.googleapis.com",
  "secretmanager.googleapis.com",
]

enable_firestore          = true
create_firestore_database = true
firestore_location_id     = "nam5"

manage_oauth_secrets         = false
create_oauth_secret_versions = false

google_oauth_client_id     = null
google_oauth_client_secret = null

google_oauth_redirect_uri = "http://localhost:8000/oauth/google/callback"

backend_service_account_email = null
