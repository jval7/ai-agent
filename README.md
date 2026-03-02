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

Stop containers:

```bash
make docker-down
```

By default, domain state is persisted to `data/memory_store.json`. You can disable it by setting:

```bash
MEMORY_JSON_FILE_PATH=
```

Development-only endpoints are enabled by default (`ENABLE_DEV_ENDPOINTS=true`).

For Meta webhook verification, use a single platform token:

```bash
META_WEBHOOK_VERIFY_TOKEN=dev-meta-webhook-verify-token
```

Configure that same value once in Meta for the webhook callback.

For post-OAuth Cloud API provisioning, configure a 6-digit phone registration PIN:

```bash
META_PHONE_REGISTRATION_PIN=123456
```

During embedded signup completion, backend now runs:

- `POST /{WABA_ID}/subscribed_apps`
- `POST /{PHONE_NUMBER_ID}/register`

OAuth callback return URL for browser redirect after Meta permissions:

```bash
FRONTEND_APP_BASE_URL=http://localhost:5173
```

For LLM responses with Gemini on Vertex AI, configure:

```bash
GEMINI_PROJECT_ID=your_gcp_project_id
GEMINI_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_OUTPUT_TOKENS=512
```

## Hybrid OAuth (Terraform)

Si quieres manejar Google OAuth con esquema hibrido (client manual + secretos/permisos por IaC):

- Revisa: `infra/terraform/hybrid_oauth/README.md`

## GCP Project Bootstrap (Terraform)

Si quieres crear un proyecto nuevo de GCP con Terraform (cuenta principal, sin service account por ahora):

- Revisa: `infra/terraform/project_bootstrap/README.md`

## Logging

Backend uses JSON logs to `stdout` with request correlation.

- Incoming `X-Request-ID` is reused; if absent, backend generates one.
- Every HTTP response includes `X-Request-ID`.
- Unhandled exceptions return:
  - `500`
  - `{"detail":"internal server error","request_id":"<id>"}`
- Traceback is logged only on server side.

Environment flags:

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
