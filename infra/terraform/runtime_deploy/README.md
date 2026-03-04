# Runtime Deploy (Cloud Run + Artifact Registry)

Este stack administra el runtime de la app:

1. APIs necesarias de runtime.
2. Artifact Registry (Docker).
3. Cloud Run service del backend.
4. Secret Manager: secreto JSON unico `AI_AGENT_APP_CONFIG_JSON` para config de app.
5. Acceso de runtime SA a secretos usados por la app.

## Requisitos

1. Haber ejecutado `infra/terraform/github_wif` (o tener SA/runtime/WIF listos).
2. `runtime_service_account_email` valido.

## Uso manual (opcional)

```bash
cd infra/terraform/runtime_deploy
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars` y luego:

```bash
terraform init
terraform plan
terraform apply
```

Alternativa para desarrollo local (sin pasar `-var` uno por uno):

```bash
cd infra/terraform/runtime_deploy
terraform init -backend=false
terraform apply -auto-approve \
  -var-file=env.development.json \
  -target=google_project_service.serviceusage \
  -target=google_project_service.apis \
  -target=google_secret_manager_secret.app_config_json \
  -target=google_secret_manager_secret_version.app_config_json_bootstrap \
  -target=google_secret_manager_secret_iam_member.runtime_secret_accessor
```

## Uso desde CI/CD

El workflow `.github/workflows/deploy-main.yml`:

1. Se activa en push a `main`.
2. Se autentica por WIF.
3. Construye imagen Docker y la sube a Artifact Registry.
4. Ejecuta `terraform apply` con la imagen del commit.
5. Guarda state en backend remoto GCS.

Secrets/variables de GitHub requeridos:

1. `GCP_WIF_PROVIDER`
2. `GCP_WIF_SERVICE_ACCOUNT`
3. `GCP_PROJECT_ID`
4. `GCP_REGION`
5. `GCP_ARTIFACT_REPOSITORY`
6. `RUNTIME_SERVICE_ACCOUNT_EMAIL`
7. `TF_STATE_BUCKET`
8. Opcional: `TF_STATE_PREFIX`
9. Opcional: `CLOUD_RUN_SERVICE_NAME`

## Secret JSON unico para configuracion

El stack crea un secret JSON unico y la app lo lee directo desde Secret Manager al iniciar:

1. Secret ID fijo: `AI_AGENT_APP_CONFIG_JSON`
2. La app usa ADC para resolver proyecto y leer `versions/latest`.
3. No depende de variables de entorno para configuracion funcional.

Variables Terraform relevantes:

1. `manage_app_config_secret` (default `true`)
2. `app_config_secret_bootstrap_json` (default `{}`)
3. `min_instances` (recomendado `1` para reducir cold starts)

## Bucket de state (una sola vez)

Si aun no tienes bucket de Terraform state:

```bash
PROJECT_ID="ai-agent-dev-12345"
BUCKET_NAME="ai-agent-terraform-state"

gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --project="${PROJECT_ID}" \
  --location=US \
  --uniform-bucket-level-access
```

Luego guarda `TF_STATE_BUCKET=${BUCKET_NAME}` en GitHub Secrets.
