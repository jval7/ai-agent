# Project Bootstrap (GCP)

Este stack deja todo en un solo modulo:

1. Crea proyecto GCP y lo vincula a billing.
2. Habilita APIs base del backend.
3. Crea Firestore `(default)` en modo Native (opcional).
4. Crea secretos OAuth en Secret Manager para Calendar.
5. Opcionalmente crea versiones de secretos y permisos IAM para la service account del backend.

## Requisitos

1. Permisos para crear proyectos y vincular billing.
2. `gcloud` y `terraform` instalados.
3. Login en tu cuenta principal:

```bash
gcloud auth login
gcloud auth application-default login
```

## 1) Obtener billing account ID

```bash
gcloud billing accounts list
```

## 2) Configurar variables

```bash
cd infra/terraform/project_bootstrap
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars`:

1. `project_id`
2. `project_name`
3. `billing_account_id`
4. `org_id` o `folder_id` solo si aplica (en cuenta personal ambos `null`)
5. Firestore:
   - `enable_firestore = true`
   - `create_firestore_database = true`
   - `firestore_location_id = "nam5"`
6. OAuth + secretos:
   - `manage_oauth_secrets = true`
   - `create_oauth_secret_versions = false` (recomendado)
   - `backend_service_account_email` (opcional, para Cloud Run runtime SA)
   - `google_oauth_redirect_uri` segun entorno

## 3) Plan y apply

```bash
terraform init
terraform plan
terraform apply
```

## 4) Paso manual unico: OAuth client de Calendar

En Google Cloud Console:

1. Configura `OAuth consent screen`.
2. Crea credencial `OAuth client ID` tipo `Web application`.
3. Agrega redirect URI:
   - local: `http://localhost:8000/oauth/google/callback`
   - prod: `https://<tu-api>/oauth/google/callback`
4. Guarda:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`

## 5) Cargar valores de secretos (recomendado)

Con `create_oauth_secret_versions=false`, Terraform crea solo contenedores de secretos.
Carga valores despues:

```bash
PROJECT_ID="your-gcp-project-id"
GOOGLE_OAUTH_CLIENT_ID="..."
GOOGLE_OAUTH_CLIENT_SECRET="..."

printf '%s' "$GOOGLE_OAUTH_CLIENT_ID" \
  | gcloud secrets versions add GOOGLE_OAUTH_CLIENT_ID \
      --project="$PROJECT_ID" \
      --data-file=-

printf '%s' "$GOOGLE_OAUTH_CLIENT_SECRET" \
  | gcloud secrets versions add GOOGLE_OAUTH_CLIENT_SECRET \
      --project="$PROJECT_ID" \
      --data-file=-
```

## 6) Bootstrap opcional rapido (dev)

Si quieres que Terraform cree versiones automaticamente:

1. `create_oauth_secret_versions = true`
2. Define `google_oauth_client_id` y `google_oauth_client_secret`
3. Ejecuta `terraform apply`

Nota: en este modo los valores quedan en `tfstate`.
