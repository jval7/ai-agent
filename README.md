# AI Agent MVP Backend

Backend MVP for a multi-tenant WhatsApp customer support agent built with FastAPI and hexagonal architecture.

Meta onboarding and message lifecycle (E2E): `META_BACKEND_E2E_README.md`

## Tooling

- Dependency manager: `uv`
- Linting/format: `ruff`
- Type checking: `mypy`
- Security scan: `bandit`
- Git hooks: `pre-commit`

## Quick start

```bash
uv sync --group dev
uv run pre-commit install
uv run uvicorn src.entrypoints.web.main:app --reload
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

For LLM responses, configure Anthropic:

```bash
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_VERSION=2023-06-01
ANTHROPIC_MAX_TOKENS=512
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
