# Setup manual: Ambiente Dev en GCP

Guia paso a paso para crear el ambiente de desarrollo separado de produccion.

**Produccion**: `ai-agent-calendar-2603011621`
**Desarrollo**: `ai-agent-calendar-dev`

---

## Paso 1: Crear proyecto GCP para dev

```bash
# Crear el proyecto (ajustar billing account)
gcloud projects create ai-agent-calendar-dev \
  --name="AI Agent Calendar Dev"

# Vincular billing account (necesario para habilitar APIs)
# Listar billing accounts disponibles:
gcloud billing accounts list

# Vincular (reemplazar BILLING_ACCOUNT_ID):
gcloud billing projects link ai-agent-calendar-dev \
  --billing-account=BILLING_ACCOUNT_ID
```

## Paso 2: Habilitar APIs necesarias en el proyecto dev

```bash
export DEV_PROJECT=ai-agent-calendar-dev

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  storage.googleapis.com \
  --project=$DEV_PROJECT
```

## Paso 3: Crear bucket de Terraform state (en proyecto dev)

```bash
export DEV_PROJECT=ai-agent-calendar-dev
export TF_STATE_BUCKET_DEV="${DEV_PROJECT}-tf-state"

# Crear bucket
gcloud storage buckets create "gs://${TF_STATE_BUCKET_DEV}" \
  --project=$DEV_PROJECT \
  --location=us-central1 \
  --uniform-bucket-level-access

# Habilitar versionado (protege contra state corrupto)
gcloud storage buckets update "gs://${TF_STATE_BUCKET_DEV}" \
  --versioning
```

Repetir para prod si aun no tiene bucket remoto:

```bash
export PROD_PROJECT=ai-agent-calendar-2603011621
export TF_STATE_BUCKET_PROD="${PROD_PROJECT}-tf-state"

gcloud storage buckets create "gs://${TF_STATE_BUCKET_PROD}" \
  --project=$PROD_PROJECT \
  --location=us-central1 \
  --uniform-bucket-level-access

gcloud storage buckets update "gs://${TF_STATE_BUCKET_PROD}" \
  --versioning
```

## Paso 4: Configurar Workload Identity Federation (WIF) en proyecto dev

Esto permite que GitHub Actions se autentique con GCP sin service account keys.

```bash
export DEV_PROJECT=ai-agent-calendar-dev
export GITHUB_REPO="OWNER/REPO"  # <-- Reemplazar con tu repo

# Crear pool de identidad
gcloud iam workload-identity-pools create "github-pool" \
  --project=$DEV_PROJECT \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Crear provider OIDC
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project=$DEV_PROJECT \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Obtener el nombre completo del provider (guardar para GitHub secrets)
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project=$DEV_PROJECT \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
# Output: projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

## Paso 5: Crear Service Account para deploy en proyecto dev

```bash
export DEV_PROJECT=ai-agent-calendar-dev

# SA para CI/CD (GitHub Actions)
gcloud iam service-accounts create "github-deploy" \
  --project=$DEV_PROJECT \
  --display-name="GitHub Actions Deploy"

# Roles necesarios para el SA de deploy
for role in \
  roles/run.admin \
  roles/artifactregistry.admin \
  roles/storage.admin \
  roles/secretmanager.admin \
  roles/iam.serviceAccountUser \
  roles/compute.networkAdmin \
  roles/compute.securityAdmin; do
  gcloud projects add-iam-policy-binding $DEV_PROJECT \
    --member="serviceAccount:github-deploy@${DEV_PROJECT}.iam.gserviceaccount.com" \
    --role="$role"
done

# Permitir que GitHub Actions impersone este SA via WIF
DEV_PROJECT_NUMBER=$(gcloud projects describe $DEV_PROJECT --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding \
  "github-deploy@${DEV_PROJECT}.iam.gserviceaccount.com" \
  --project=$DEV_PROJECT \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${DEV_PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"
```

## Paso 6: Crear el Secret de app config en proyecto dev

```bash
export DEV_PROJECT=ai-agent-calendar-dev

# Crear el secret vacio
echo '{}' | gcloud secrets create AI_AGENT_APP_CONFIG_JSON \
  --project=$DEV_PROJECT \
  --data-file=-

# Luego poblar con las keys de dev:
# make app-config-secret-sync-env DEPLOY_PROJECT_ID=$DEV_PROJECT APP_CONFIG_ENV_FILE=.env
```

## Paso 7: Configurar GitHub Environments

En GitHub repo > Settings > Environments, crear dos environments:

### Environment: `dev`

| Secret/Variable | Tipo | Valor |
|---|---|---|
| `GCP_WIF_PROVIDER` | Secret | `projects/DEV_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_WIF_SERVICE_ACCOUNT` | Secret | `github-deploy@ai-agent-calendar-dev.iam.gserviceaccount.com` |
| `TF_STATE_BUCKET` | Secret | `ai-agent-calendar-dev-tf-state` |
| `RUNTIME_SERVICE_ACCOUNT_EMAIL` | Secret | (default compute SA o custom) |
| `VITE_API_BASE_URL` | Variable | (URL del backend dev, se llena despues del primer deploy) |
| `TF_VAR_FRONTEND_BUCKET_NAME` | Variable | (opcional, override) |

### Environment: `prod`

Mover los secrets actuales del repo (que son globales) al environment `prod`:

| Secret/Variable | Tipo | Valor |
|---|---|---|
| `GCP_WIF_PROVIDER` | Secret | (valor actual del WIF de prod) |
| `GCP_WIF_SERVICE_ACCOUNT` | Secret | (valor actual del SA de prod) |
| `TF_STATE_BUCKET` | Secret | `ai-agent-calendar-2603011621-tf-state` |
| `RUNTIME_SERVICE_ACCOUNT_EMAIL` | Secret | (valor actual) |
| `VITE_API_BASE_URL` | Variable | (URL del backend prod) |
| `TF_VAR_FRONTEND_BUCKET_NAME` | Variable | (opcional) |

> **IMPORTANTE**: Despues de mover secrets a environments, eliminar los secrets globales del repo
> para evitar que el workflow use los incorrectos.

## Paso 8: Migrar Terraform state de prod a bucket remoto

Si prod actualmente usa state local, migrar al bucket remoto:

```bash
export PROD_PROJECT=ai-agent-calendar-2603011621
export TF_STATE_BUCKET_PROD="${PROD_PROJECT}-tf-state"

# Backend (runtime_deploy)
cd infra/terraform/runtime_deploy
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET_PROD}" \
  -backend-config="prefix=prod/runtime-deploy" \
  -migrate-state

# Frontend (frontend_spa_cdn)
cd ../frontend_spa_cdn
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET_PROD}" \
  -backend-config="prefix=prod/frontend-spa-cdn" \
  -migrate-state
```

## Paso 9: Actualizar dev.tfvars con project_id real

Editar los archivos con el project_id del proyecto creado:

- `infra/terraform/runtime_deploy/envs/dev.tfvars` — cambiar `<DEV_PROJECT_ID>` por `ai-agent-calendar-dev`
- `infra/terraform/frontend_spa_cdn/envs/dev.tfvars` — cambiar `<DEV_PROJECT_ID>` por `ai-agent-calendar-dev`

## Paso 10: Primer deploy a dev

```bash
# Opcion A: Push a main (auto-deploy a dev)
git push origin main

# Opcion B: Workflow dispatch manual
# GitHub Actions > Deploy to GCP > Run workflow > environment: dev
```

## Checklist de verificacion

- [ ] Proyecto GCP `ai-agent-calendar-dev` creado y con billing
- [ ] APIs habilitadas en proyecto dev
- [ ] Bucket TF state creado en proyecto dev (con versionado)
- [ ] Bucket TF state creado en proyecto prod (con versionado)
- [ ] WIF pool + provider configurado en proyecto dev
- [ ] SA `github-deploy` creado con roles y binding WIF
- [ ] Secret `AI_AGENT_APP_CONFIG_JSON` creado en proyecto dev
- [ ] GitHub Environment `dev` creado con secrets
- [ ] GitHub Environment `prod` creado con secrets (migrados de repo-level)
- [ ] Secrets globales del repo eliminados
- [ ] State de prod migrado a bucket remoto
- [ ] `dev.tfvars` actualizados con project_id real
- [ ] Primer deploy a dev exitoso
