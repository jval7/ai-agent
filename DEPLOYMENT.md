# Despliegue (Infra + Codigo)

Guia operativa para desplegar backend y frontend de `ai-agent` en GCP usando los comandos del repo.

## Requisitos
- `gcloud`, `terraform`, `docker`, `npm`, `uv`
- Sesion activa en GCP:
  - `gcloud auth login`
  - `gcloud auth application-default login`
  - `gcloud config set project ai-agent-calendar-2603011621`

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

## Verificacion rapida post-deploy
- Backend docs: `https://<cloud-run-url>/docs`
- Health: `https://<cloud-run-url>/healthz`
- Frontend: URL en `.make-flow/deploy/front.env` (`DEPLOY_FRONTEND_URL=...`)

## Regla de commits
- No usar `--no-verify`.
- Si falla pre-commit/hooks, arreglar errores y volver a commitear (o `git commit --amend`).
