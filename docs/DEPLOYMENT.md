# Despliegue (Infra + Codigo)

Guia operativa para desplegar backend y frontend de `ai-agent` en GCP usando los comandos del repo.

## Requisitos
- `gcloud`, `terraform`, `docker`, `npm`, `uv`
- Sesion activa en GCP:
  - `gcloud auth login`
  - `gcloud auth application-default login`
  - `gcloud config set project ai-agent-calendar-2603011621`

## Archivos de infraestructura local

### Dockerfiles
- `Dockerfile.backend` — imagen de backend (Python 3.11-slim + uv).
- `frontend/Dockerfile` — imagen de frontend (Node 22-alpine).

### docker-compose.yml
- Servicios: `backend` + `frontend` para desarrollo local.
- Uso: `docker compose up` (no es el flujo principal de desarrollo; para dev local preferir `make fe-dev` + `uv run uvicorn ...`).

### Flujo Terraform local
- Los módulos Terraform viven en `infra/terraform/` (`runtime_deploy`, `frontend_spa_cdn`).
- Al hacer deploy, Make copia via rsync a `.make-flow/deploy/terraform/{module}_local/` como working copies.
- Los state files se persisten en `.make-flow/deploy/state/*.tfstate`.
- No editar archivos en `.make-flow/` directamente; editar siempre en `infra/terraform/`.

## Variables y archivos usados por Make
- Estado local de terraform: `.make-flow/deploy/state/*.tfstate`
- Salida backend deploy: `.make-flow/deploy/back.env`
- Salida frontend deploy: `.make-flow/deploy/front.env`
- API base para comandos make: `.secrets/make_api_base.env`
- Credenciales para comandos make: `.secrets/make_credentials.env`

## Despliegue de backend
Comando recomendado:

```bash
make deploy-back
```

Que hace:
- Provisiona/actualiza runtime infra con Terraform (`infra/terraform/runtime_deploy`)
- Construye y sube imagen Docker a Artifact Registry
- Actualiza Cloud Run
- Guarda URL resultante en `.make-flow/deploy/back.env`

## Despliegue de frontend (SPA + CDN)
Comando recomendado:

```bash
make deploy-front
```

Que hace:
- `deploy-front-infra`: crea/actualiza bucket + LB/CDN (`infra/terraform/frontend_spa_cdn`)
- `deploy-front-upload`: build del frontend y upload de `frontend/dist`

Alternativa por pasos:

```bash
make deploy-front-infra
make deploy-front-upload
```

## Desplegar todo

```bash
make deploy-all
```

Ejecuta: frontend infra -> backend -> frontend upload.

## Configuracion runtime (Secret Manager JSON)
El backend lee configuracion desde `AI_AGENT_APP_CONFIG_JSON`.

Upsert de una llave:

```bash
make app-config-secret-upsert \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_PAIR='META_WEBHOOK_VERIFY_TOKEN:dev-meta-webhook-verify-token123'
```

Sincronizar desde `.env`:

```bash
make app-config-secret-sync-env \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_ENV_FILE=.env
```

Despues de cambiar secret, redeploy backend:

```bash
make deploy-back
```

## Comandos utiles de operacion local
Guardar URL backend para comandos make:

```bash
make save-api-base API_BASE=https://<cloud-run-url>
```

Reset de memoria de chat contra backend desplegado:

```bash
make chat-memory-reset
```

## APIs de GCP gestionadas por Terraform
Las APIs del proyecto se declaran en `infra/terraform/project_bootstrap/variables.tf` (`enable_apis`).
Si se necesita habilitar una nueva API de GCP, agregarla ahi para que Terraform sea la fuente de verdad.

APIs actuales: `calendar-json`, `secretmanager`, `stitch` (Google Stitch - diseño UI con AI).

## Verificacion rapida post-deploy
- Backend docs: `https://<cloud-run-url>/docs`
- Health: `https://<cloud-run-url>/healthz`
- Frontend: URL en `.make-flow/deploy/front.env` (`DEPLOY_FRONTEND_URL=...`)

## Regla de commits
Ver "Principios de Trabajo" en `CLAUDE.md` (fuente canónica).
