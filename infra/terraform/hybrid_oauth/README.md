# Hybrid OAuth Bootstrap (Google Calendar)

Este stack implementa el esquema hibrido:

- Paso manual unico: crear OAuth Client ID/Secret en Google Cloud Console.
- Terraform: habilitar APIs, crear secretos y permisos.
- Carga de valores secretos: manual recomendada (sin guardar secretos en `tfstate`) u opcional por Terraform.

## 1) Crear OAuth client manualmente

En Google Cloud Console:

1. Habilita `Google Calendar API`.
2. Configura `OAuth consent screen`.
3. Crea credencial `OAuth client ID` tipo `Web application`.
4. Agrega redirect URI:
   - local: `http://localhost:8000/oauth/google/callback`
   - prod: `https://<tu-api>/oauth/google/callback`
5. Guarda:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`

## 2) Inicializar Terraform

```bash
cd infra/terraform/hybrid_oauth
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## 3) Cargar secretos (modo recomendado)

Con `create_secret_versions=false` (default), Terraform solo crea contenedores de secretos.
Luego carga valores manualmente:

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

## 4) Modo bootstrap opcional (rapido para dev)

Si prefieres que Terraform cree versiones automaticamente:

1. En `terraform.tfvars`:
   - `create_secret_versions = true`
   - completa `google_oauth_client_id` y `google_oauth_client_secret`
2. Ejecuta `terraform apply`.

Nota: en este modo, los valores secretos quedan en `tfstate`.

## 5) Conectar backend a los secretos

Este repo local usa `.env` para Docker. Para local:

```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/google/callback
```

Si despliegas en Cloud Run, ejemplo:

```bash
gcloud run services update ai-agent-backend \
  --region us-central1 \
  --set-secrets GOOGLE_OAUTH_CLIENT_ID=GOOGLE_OAUTH_CLIENT_ID:latest \
  --set-secrets GOOGLE_OAUTH_CLIENT_SECRET=GOOGLE_OAUTH_CLIENT_SECRET:latest \
  --set-env-vars GOOGLE_OAUTH_REDIRECT_URI=https://<tu-api>/oauth/google/callback
```

## 6) Verificacion API

Con backend corriendo y token JWT valido:

```bash
curl -sS -X POST http://localhost:8000/v1/google-calendar/oauth/session \
  -H "Authorization: Bearer <access_token>" | jq
```

Debe retornar `state` y `connect_url`.
