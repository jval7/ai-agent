# Backend Context (MVP)

## Estado actual
- Backend MVP multi-tenant para atención por WhatsApp.
- Stack: FastAPI + arquitectura hexagonal + persistencia in-memory con snapshot JSON.
- Providers activos:
  - WhatsApp: Meta Cloud API.
  - LLM: Anthropic (`ANTHROPIC_*`).

## Estructura de capas
- `src/entrypoints/web`: capa HTTP (routers, handlers, dependencias auth).
- `src/services`: casos de uso y DTOs principales.
- `src/ports`: contratos/interfaces para adapters.
- `src/adapters/outbound`: implementaciones concretas (Meta, Anthropic, seguridad, in-memory).
- `src/domain`: entidades/agregados Pydantic.
- `src/infra`: settings + wiring en `container.py`.

## Reglas de dependencia
- Flujo permitido: `entrypoints -> services -> ports <- adapters`.
- `infra/container` conecta puertos con adapters.
- `services` y `domain` no deben depender de adapters concretos.

## Funcionalidad implementada
- Auth:
  - `POST /v1/auth/register`
  - `POST /v1/auth/login`
  - `POST /v1/auth/refresh`
  - `POST /v1/auth/logout`
- Prompt del agente:
  - `GET /v1/agent/system-prompt`
  - `PUT /v1/agent/system-prompt`
- Onboarding WhatsApp:
  - `POST /v1/whatsapp/embedded-signup/session`
  - `POST /v1/whatsapp/embedded-signup/complete`
  - `GET /oauth/meta/callback`
  - `GET /v1/whatsapp/connection`
- Webhook:
  - `GET /v1/webhooks/whatsapp` (verify token)
  - `POST /v1/webhooks/whatsapp` (procesamiento inbound)
- Conversaciones:
  - `GET /v1/conversations`
  - `GET /v1/conversations/{conversation_id}/messages`
  - `PUT /v1/conversations/{conversation_id}/control-mode`
- Blacklist por tenant:
  - `GET /v1/blacklist`
  - `POST /v1/blacklist`
  - `DELETE /v1/blacklist/{whatsapp_user_id}`
- Dev:
  - `POST /v1/dev/memory/reset`
  - `GET /healthz`

## Lógica clave en webhook
- Resuelve tenant por `phone_number_id`.
- Deduplica por `provider_event_id`.
- Si contacto está en blacklist: ignora conversación/mensajes/IA y marca procesado.
- Si evento es de dueño (`OWNER_APP`, coexistence echo):
  - guarda mensaje `role=human_agent`,
  - fuerza conversación a `HUMAN`.
- Si evento es cliente (`CUSTOMER`):
  - guarda inbound,
  - si conversación está en `HUMAN`, no responde IA,
  - si está en `AI`, genera respuesta con Anthropic y envía por WhatsApp.

## Persistencia actual
- Store in-memory compartido entre repositorios.
- Snapshot JSON configurable con `MEMORY_JSON_FILE_PATH` (default `data/memory_store.json`).
- Reinicio conserva estado solo si snapshot está habilitado.

## Logging y errores
- Logging estructurado JSON en `stdout`.
- Correlación por `X-Request-ID`:
  - si llega desde cliente/proxy, se reutiliza;
  - si no llega, se genera en middleware.
- Todas las respuestas HTTP incluyen header `X-Request-ID`.
- Errores no controlados en entrypoints:
  - response `500` con body `{"detail":"internal server error","request_id":"..."}`,
  - traceback completo solo en logs del servidor.
- Config por env:
  - `LOG_LEVEL` (default `INFO`)
  - `LOG_INCLUDE_REQUEST_SUMMARY` (default `false`)

## Comandos útiles
- Setup:
  - `uv sync --group dev`
  - `uv run pre-commit install`
- Run API:
  - `uv run uvicorn src.entrypoints.web.main:app --reload`
- Checks:
  - `make static-checks`
  - `uv run pytest tests/services -q`
- Flujo OAuth local:
  - `make oauth-flow`
  - `make memory-reset`
