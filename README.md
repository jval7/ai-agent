# AI Agent MVP

Backend MVP for a multi-tenant WhatsApp customer support agent built with FastAPI and hexagonal architecture.

Meta onboarding and message lifecycle (E2E): `META_BACKEND_E2E_README.md`

## Tooling

- Dependency manager: `uv`
- Linting/format: `ruff`
- Type checking: `mypy`
- Security scan: `bandit`
- Git hooks: `pre-commit`

Frontend lives in `frontend/` and uses React + TypeScript strict + hexagonal folders.

## Quick start

```bash
uv sync --group dev
uv run pre-commit install
uv run uvicorn src.entrypoints.web.main:app --reload
```

Frontend (separate terminal):

```bash
make fe-install
make fe-dev
```

## Run with Docker

```bash
make docker-up-build
```

URLs:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

In local Docker runs, backend CORS can be overridden with:

- `CORS_ALLOWED_ORIGINS_OVERRIDE` (comma-separated list)

Stop containers:

```bash
make docker-down
```

Domain state is persisted in Firestore and all app runtime config is read from Secret Manager.
Required local setup:

```bash
gcloud auth application-default login
gcloud config set project your_gcp_project_id
```

If you run locally with ADC JSON credentials:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your/adc.json
```

During embedded signup completion, backend now runs:

- `POST /{WABA_ID}/subscribed_apps`
- `POST /{PHONE_NUMBER_ID}/register`

Config values like `JWT_SECRET`, `META_*`, `GEMINI_*`, CORS, URLs and limits must be stored in:
- `AI_AGENT_APP_CONFIG_JSON`

## GCP Project Bootstrap (Terraform)

Si quieres crear un proyecto nuevo de GCP con Terraform (Firestore + secretos OAuth en el mismo stack):

- Revisa: `infra/terraform/project_bootstrap/README.md`

## CI/CD Deploy to GCP (WIF + Terraform)

El deploy automatico en `push` a `main` usa GitHub OIDC + Workload Identity Federation (sin JSON keys).

1. Bootstrap WIF + service accounts:
   - `infra/terraform/github_wif/README.md`
2. Stack runtime (Cloud Run + Artifact Registry):
   - `infra/terraform/runtime_deploy/README.md`
3. Stack frontend SPA (Cloud Storage + HTTPS LB + Cloud CDN):
   - `infra/terraform/frontend_spa_cdn/README.md`
4. Workflows:
   - Backend: `.github/workflows/deploy-main.yml`
   - Frontend SPA CDN: `.github/workflows/deploy-frontend-main.yml`

Secrets/variables para backend workflow (`deploy-main.yml`):

1. `GCP_WIF_PROVIDER` (secret)
2. `GCP_WIF_SERVICE_ACCOUNT` (secret)
3. `GCP_PROJECT_ID` (secret)
4. `GCP_REGION` (secret)
5. `GCP_ARTIFACT_REPOSITORY` (secret)
6. `RUNTIME_SERVICE_ACCOUNT_EMAIL` (secret)
7. `TF_STATE_BUCKET` (secret)
8. `TF_STATE_PREFIX` (secret, opcional)
9. `CLOUD_RUN_SERVICE_NAME` (secret, opcional)

Secrets/variables para frontend workflow (`deploy-frontend-main.yml`):

1. `GCP_WIF_PROVIDER` (secret)
2. `GCP_WIF_SERVICE_ACCOUNT` (secret)
3. `GCP_PROJECT_ID` (secret)
4. `TF_STATE_BUCKET` (secret)
5. `TF_STATE_PREFIX_FRONTEND` (secret, opcional)
6. `TF_VAR_FRONTEND_DOMAINS_JSON` (variable, requerida; ejemplo `["app.tudominio.com"]`)
7. `VITE_API_BASE_URL` (variable, requerida; URL publica del backend)
8. `TF_VAR_FRONTEND_BUCKET_NAME` (variable, opcional)
9. `TF_VAR_FRONTEND_BUCKET_LOCATION` (variable, opcional)
10. `TF_VAR_FRONTEND_RESOURCE_NAME_PREFIX` (variable, opcional)

## Single JSON Secret Config

Backend supports a single JSON secret loaded directly from Secret Manager at startup.

Use Terraform runtime stack to inject it, then upsert keys with Make:

```bash
make app-config-secret-upsert \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_KEY=META_REDIRECT_URI \
  APP_CONFIG_VALUE=https://your-domain/oauth/meta/callback
```

Single pair format (`LLAVE:VALOR`):

```bash
make app-config-secret-upsert \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_PAIR='META_REDIRECT_URI:https://your-domain/oauth/meta/callback'
```

Typed values (number, bool, array) using JSON:

```bash
make app-config-secret-upsert \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_KEY=CONTEXT_MESSAGE_LIMIT \
  APP_CONFIG_VALUE_JSON=50
```

Sync runtime keys from a local `.env` file into the JSON secret:

```bash
make app-config-secret-sync-env \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_ENV_FILE=.env
```

If you also want to remove synced runtime keys from `.env` after upload:

```bash
make app-config-secret-sync-env \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_ENV_FILE=.env \
  APP_CONFIG_PRUNE_ENV=true
```

## Logging

Backend uses JSON logs to `stdout` with request correlation.

- Incoming `X-Request-ID` is reused; if absent, backend generates one.
- Every HTTP response includes `X-Request-ID`.
- Unhandled exceptions return:
  - `500`
  - `{"detail":"internal server error","request_id":"<id>"}`
- Traceback is logged only on server side.

Config keys (inside `AI_AGENT_APP_CONFIG_JSON`):

```bash
LOG_LEVEL=INFO
LOG_INCLUDE_REQUEST_SUMMARY=false
```

## Landing for Meta review (separate deploy)

Static landing files now live outside `src` in:

- `landing/index.html`
- `landing/privacy.html`
- `landing/terms.html`
- `landing/styles.css`

Deploy that folder as a standalone static site under HTTPS and use:

- `https://tu-dominio.com/`
- `https://tu-dominio.com/privacy.html`
- `https://tu-dominio.com/terms.html`

in your Meta Business profile and review flow.

## Run checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run bandit -c pyproject.toml -r src
uv run pytest
```

Full repo checks:

```bash
make checks
```

## Simulate WhatsApp inbound message (dev)

You can simulate an inbound customer message through webhook parsing and then inspect the resulting conversation:

```bash
make simulate-whatsapp-message MESSAGE="Hola, necesito ayuda con mi pedido"
```

Optional vars:

- `SIM_WA_USER_ID` (default: `573001234567`)
- `SIM_WA_USER_NAME` (default: `Cliente Demo`)
- `SIM_PROVIDER_MESSAGE_ID` (default: auto-generated)
