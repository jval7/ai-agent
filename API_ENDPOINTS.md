# API Endpoints (MVP WhatsApp Agent)

Este documento describe qué hace cada endpoint del backend.

## Convenciones

- Base URL local: `http://localhost:8000`
- Auth: `Authorization: Bearer <access_token>`
- Content-Type JSON: `application/json`
- Error mapping global:
  - `400`: estado inválido (`InvalidStateError`)
  - `401`: autenticación inválida/faltante (`AuthenticationError`)
  - `403`: autorización inválida (`AuthorizationError`)
  - `404`: entidad no encontrada (`EntityNotFoundError`)
  - `409`: conflicto por duplicado (`DuplicateWebhookEventError`)
  - `502`: error de proveedor externo (`ExternalProviderError`)
  - `422`: validación de request por FastAPI/Pydantic

---

## Health

### `GET /healthz`
- Auth: no
- Qué hace: confirma que la API está viva.
- Response example:
```json
{
  "status": "ok"
}
```

---

## Auth

### `POST /v1/auth/register`
- Auth: no
- Qué hace: crea `Tenant` + `User owner`, inicializa prompt por defecto y devuelve tokens.
- Request body:
```json
{
  "tenant_name": "Acme",
  "email": "owner@acme.com",
  "password": "supersecret"
}
```
- Response body:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in_seconds": 1800
}
```

### `POST /v1/auth/login`
- Auth: no
- Qué hace: valida credenciales y emite tokens.
- Request body:
```json
{
  "email": "owner@acme.com",
  "password": "supersecret"
}
```
- Response body: igual que `register`.

### `POST /v1/auth/refresh`
- Auth: no
- Qué hace: rota refresh token y devuelve nuevo par de tokens.
- Request body:
```json
{
  "refresh_token": "..."
}
```
- Response body: igual que `register`.

### `POST /v1/auth/logout`
- Auth: sí (access token)
- Qué hace: revoca refresh token enviado en el body.
- Request body:
```json
{
  "refresh_token": "..."
}
```
- Response: `204 No Content`.

---

## Agent

### `GET /v1/agent/system-prompt`
- Auth: sí
- Qué hace: retorna system prompt del tenant autenticado.
- Response body:
```json
{
  "tenant_id": "...",
  "system_prompt": "..."
}
```

### `PUT /v1/agent/system-prompt`
- Auth: sí
- Qué hace: actualiza system prompt del tenant autenticado.
- Request body:
```json
{
  "system_prompt": "Eres un agente de soporte claro y directo"
}
```
- Response body:
```json
{
  "tenant_id": "...",
  "system_prompt": "Eres un agente de soporte claro y directo"
}
```

---

## WhatsApp Onboarding

### `POST /v1/whatsapp/embedded-signup/session`
- Auth: sí
- Qué hace: crea estado de onboarding (`state`) y devuelve URL para iniciar Embedded Signup.
- Response body:
```json
{
  "state": "...",
  "connect_url": "https://www.facebook.com/..."
}
```

### `POST /v1/whatsapp/embedded-signup/complete`
- Auth: sí
- Qué hace: completa conexión WhatsApp para el tenant con `code` + `state`.
- Request body:
```json
{
  "code": "...",
  "state": "..."
}
```
- Response body:
```json
{
  "tenant_id": "...",
  "status": "CONNECTED",
  "phone_number_id": "...",
  "business_account_id": "..."
}
```
- Nota local/dev: soporta `code` mock con formato:
  - `mock::<phone_number_id>::<business_account_id>::<access_token>`

### `GET /oauth/meta/callback`
- Auth: no (redirección de Meta)
- Qué hace: completa automáticamente Embedded Signup usando `code` + `state` del query string.
- Query params esperados:
  - `code`
  - `state`
- Response:
  - `200 HTML`: conexión completada
  - `4xx/5xx HTML`: error de validación/estado/proveedor
- Uso recomendado:
  - Configurar esta ruta como `META_REDIRECT_URI` en Meta para evitar copy/paste manual de `code` y `state`.

### `GET /v1/whatsapp/connection`
- Auth: sí
- Qué hace: retorna estado actual de conexión WhatsApp del tenant.
- Response body:
```json
{
  "tenant_id": "...",
  "status": "DISCONNECTED|PENDING|CONNECTED",
  "phone_number_id": "...",
  "business_account_id": "..."
}
```

### `GET /v1/whatsapp/dev/verify-token`
- Auth: sí
- Qué hace: retorna el `verify_token` global de plataforma para configurar verificación de webhook en Meta (uso dev).
- Response body:
```json
{
  "verify_token": "..."
}
```

### `POST /v1/dev/memory/reset`
- Auth: sí
- Qué hace: limpia memoria en caliente del proceso (tenants, users, conversaciones, eventos) y persiste snapshot vacío.
- Uso: desarrollo local para resetear estado sin reiniciar la API.
- Response body:
```json
{
  "status": "reset"
}
```

---

## Webhooks (Meta)

### `GET /v1/webhooks/whatsapp`
- Auth: no (llamado por Meta)
- Qué hace: verificación inicial del webhook (`hub.challenge`).
- Query params esperados:
  - `hub.mode`
  - `hub.verify_token`
  - `hub.challenge`
- Validación:
  - `hub.verify_token` debe ser igual a `META_WEBHOOK_VERIFY_TOKEN`.
- Response: texto plano con el valor de `hub.challenge` si la verificación es correcta.

### `POST /v1/webhooks/whatsapp`
- Auth: no (llamado por Meta)
- Qué hace:
  - parsea eventos de mensaje entrante
  - resuelve tenant por `phone_number_id`
  - deduplica por `provider_event_id`
  - guarda mensaje inbound
  - genera respuesta con Anthropic
  - envía respuesta por WhatsApp
  - guarda outbound y marca evento procesado
- Request body: payload oficial de Meta.
- Response body:
```json
{
  "status": "processed"
}
```
- Nota: actualmente solo procesa mensajes de tipo `text`.

---

## Conversations

### `GET /v1/conversations`
- Auth: sí
- Qué hace: lista conversaciones del tenant autenticado, ordenadas por `updated_at` descendente.
- Response body:
```json
{
  "items": [
    {
      "conversation_id": "...",
      "whatsapp_user_id": "...",
      "last_message_preview": "...",
      "updated_at": "2026-02-14T00:00:00Z"
    }
  ]
}
```

### `GET /v1/conversations/{conversation_id}/messages`
- Auth: sí
- Qué hace: retorna historial de mensajes de una conversación del tenant autenticado.
- Response body:
```json
{
  "items": [
    {
      "message_id": "...",
      "conversation_id": "...",
      "role": "user|assistant|system",
      "direction": "INBOUND|OUTBOUND",
      "content": "...",
      "created_at": "2026-02-14T00:00:00Z"
    }
  ]
}
```

---

## Flujo mínimo recomendado (manual)

1. `POST /v1/auth/register`
2. `POST /v1/whatsapp/embedded-signup/session`
3. `POST /v1/whatsapp/embedded-signup/complete`
4. `GET /v1/whatsapp/dev/verify-token` (solo dev; en producción usar directamente `META_WEBHOOK_VERIFY_TOKEN`)
5. `GET /v1/whatsapp/connection`
6. Enviar mensaje de prueba en WhatsApp
7. `GET /v1/conversations`
8. `GET /v1/conversations/{conversation_id}/messages`
