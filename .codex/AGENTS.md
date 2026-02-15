# AI-Agent MVP Context

## Reference Docs
- Backend: `/Users/jhonvalderrama/Documents/repos/ai-agent/BACKEND_CONTEXT.md`
- Frontend: `/Users/jhonvalderrama/Documents/repos/ai-agent/FRONTEND_PLAN.md`
- UI workflow: frontend design iterations are capture-driven (user shares screenshots, implementation updates UI in code).

## Current Scope
- Backend MVP only (FastAPI + hexagonal architecture).
- Multi-tenant WhatsApp support agent with tenant isolation.
- Persistence is local in-memory plus JSON snapshot (process restart survives if snapshot is enabled).

## Architecture (important)
- `src/entrypoints/web`: inbound HTTP only (routers, request/response mapping, exception handlers). No business rules.
- `src/services`: use cases, orchestration, authz checks, tenant isolation, and most DTOs.
- `src/ports`: contracts for repositories/providers. Services depend on ports, not concrete adapters.
- `src/adapters/outbound`: concrete implementations of ports (in-memory repos, Meta WhatsApp, Anthropic, JWT/hash).
- `src/domain`: Pydantic entities/aggregates with core invariants (`Tenant`, `User`, `Conversation`, `Message`, etc.).
- `src/infra`: composition root and runtime wiring (`settings.py`, `container.py`, system adapters).


### Request Flow (E2E)
- HTTP request enters router in `entrypoints/web`.
- Router resolves `AppContainer` + auth claims, then calls one service use case.
- Service coordinates domain + repository/provider ports.
- Bound adapter executes concrete I/O (memory store, Meta API, Anthropic API).
- Service returns DTO; router serializes HTTP response.

### Persistence Shape (current MVP)
- Single in-memory store shared by repository adapters.
- Concurrency protection with `threading.RLock`.
- Optional JSON snapshot on disk for restart persistence (`MEMORY_JSON_FILE_PATH`).
- No SQL/NoSQL in this phase.

### How to Extend Safely
- New external integration: add port, implement adapter, wire it in `infra/container.py`, test service with mocked port.
- New endpoint: add router in `entrypoints/web`, keep mapping thin, place behavior in a service use case.
- Keep DTOs mostly in `src/services/dto`.

## Core Behaviors Implemented
- Auth: register/login/refresh/logout with JWT claims (`sub`, `tenant_id`, `role`, `exp`, `jti`).
- Agent profile: get/update system prompt per tenant.
- WhatsApp onboarding: Embedded Signup session/complete + OAuth callback (`/oauth/meta/callback`).
- Webhook processing:
  - dedupe by provider event id,
  - tenant resolution by `phone_number_id`,
  - blacklist by `(tenant_id, wa_user_id)`,
  - conversation control mode (`AI` / `HUMAN`),
  - coexistence owner echo (`source=OWNER_APP`) forces `HUMAN` and stores `role=human_agent`.
- Conversation APIs: list conversations/messages + manual control-mode switch.
- Blacklist APIs: list/add/delete entries per tenant (owner-only).

## Providers
- WhatsApp: Meta Cloud API adapter.
- LLM: Anthropic adapter (`ANTHROPIC_*` env vars). Gemini is not active.

## Persistence / Dev Ops
- Store snapshot file: `MEMORY_JSON_FILE_PATH` (default `data/memory_store.json`).
- Dev reset endpoint: `POST /v1/dev/memory/reset` (enabled by `ENABLE_DEV_ENDPOINTS=true`).
- Make commands:
  - `make oauth-flow`
  - `make memory-reset`
  - `make static-checks`

## Quality Gates
- Static checks: ruff + mypy + bandit (`make static-checks`).
- Tests focus: service layer with mocked adapters (`uv run pytest tests/services -q`).

## Engineering Rules
1. **No hasattr/getattr**: Never use `hasattr()`, `getattr()` or similar reflection.
2. **Module imports only**: Import modules, not objects directly.
3. **Hexagonal architecture**: Use clean architecture principles.
4. **No global statement**: Never use `global` keyword.
5. **Type hints with `|`**: Use `str | None`, not `Optional[str]`.
6. **Imports at top**: Keep all imports at file top only.
7. **Always use Pydantic**: Use Pydantic for all data models.
8. **Specific exceptions**: Avoid catching generic `Exception`; catch specific exception types.
9. **Follow the Zen of Python**.
