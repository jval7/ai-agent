# API Endpoints (Agendachat backend)

Este documento describe qué hace cada endpoint del backend.

Fuente de verdad: `src/entrypoints/web/routers/` + `src/services/dto/`. La app se arma en
`src/entrypoints/web/main.py`; el schema OpenAPI vivo está en `/docs`.

## Convenciones

- Base URL local: `http://localhost:8000`
- Auth: `Authorization: Bearer <access_token>`
- Content-Type JSON: `application/json`
- Roles (`src/services/constants.py`): `professional` para el panel del tenant, `admin` para
  `/v1/admin/**` (`require_admin_claims`).
- Error mapping global (`exceptions/http_exception_handlers.py`):
  - `400`: estado inválido (`InvalidStateError`)
  - `401`: autenticación inválida/faltante (`AuthenticationError`)
  - `403`: autorización inválida (`AuthorizationError`)
  - `404`: entidad no encontrada (`EntityNotFoundError`)
  - `409`: conflicto por duplicado (`DuplicateWebhookEventError`)
  - `502`: error de proveedor externo (`ExternalProviderError`)
  - `422`: validación de request por FastAPI/Pydantic
- Rate limiting (`slowapi`, activo si `rate_limit_enabled`): login 5/min, refresh y logout 10/min,
  accept-invite 5/min, password-reset request 3/min y confirm 5/min, webhook verify 30/min,
  webhook receive 120/min.

## Routers registrados

| Router | Prefijo | Condición de registro |
|--------|---------|-----------------------|
| health | — (`/healthz`, `/readyz`) | siempre |
| admin | `/v1/admin` | siempre (requiere rol admin) |
| auth | `/v1/auth` | siempre |
| agent | `/v1/agent` | siempre |
| blacklist | `/v1/blacklist` | siempre |
| whatsapp | `/v1/whatsapp` | siempre |
| whatsapp templates | `/v1/whatsapp/templates` | siempre |
| official templates | `/v1/whatsapp/templates/official` | siempre |
| google calendar | `/v1/google-calendar` | siempre |
| onboarding | `/v1/onboarding` | siempre |
| webhooks | `/v1/webhooks` | siempre |
| conversations | `/v1/conversations` | siempre |
| patients | `/v1/patients` | siempre |
| manual appointments | `/v1/manual-appointments` | siempre |
| reminders | `/v1/reminders` | siempre |
| events (SSE) | `/v1/events` | siempre |
| scheduling | rutas sueltas `/v1/scheduling-requests`, `/v1/conversations/.../scheduling/...` | siempre |
| internal | `/v1/internal` | siempre (llamado por Cloud Tasks) |
| settings | `/v1/settings` | siempre |
| tags | rutas sueltas `/v1/tags`, `/v1/conversations/{id}/tags/{tag_id}` | siempre |
| tenant | `/v1/tenant` | siempre |
| oauth callbacks | `/oauth/**` | siempre |
| dev | `/v1/dev` | solo si `enable_dev_endpoints` |
| eval | `/v1/eval` | solo si `eval_endpoints_enabled` |

---

## Health

### `GET /healthz`
- Auth: no
- Qué hace: liveness shallow. Confirma que el proceso está vivo, sin tocar dependencias.
- Response:
```json
{"status": "ok"}
```

### `GET /readyz`
- Auth: no
- Qué hace: readiness. Chequea Firestore con timeout de 1.5s.
- Response `200` (ok) / `503` (degraded):
```json
{
  "status": "ok",
  "checks": [
    {"name": "firestore", "status": "ok", "latency_ms": 42, "message": null}
  ]
}
```

---

## Auth

### `GET /v1/auth/me`
- Auth: sí
- Qué hace: retorna la identidad del token actual. Lo usa el frontend para resolver rol (profesional vs admin).
- Response:
```json
{
  "user_id": "...",
  "email": "professional@acme.com",
  "role": "professional",
  "tenant_id": "..."
}
```

### `POST /v1/auth/login`
- Auth: no
- Qué hace: valida credenciales y emite tokens.
- Request:
```json
{"email": "professional@acme.com", "password": "supersecret"}
```
- Response:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in_seconds": 1800
}
```

### `POST /v1/auth/refresh`
- Auth: no
- Qué hace: rota refresh token (rotación estricta, el anterior se revoca) y devuelve nuevo par.
- Request: `{"refresh_token": "..."}`
- Response: igual que `login`.

### `POST /v1/auth/logout`
- Auth: sí (access token)
- Qué hace: revoca el refresh token enviado en el body.
- Request: `{"refresh_token": "..."}`
- Response: `204 No Content`.

### `POST /v1/auth/accept-invite`
- Auth: no (el token de invitación es la credencial)
- Qué hace: completa el alta de un profesional invitado: consume el token de setup, fija la contraseña y devuelve sesión iniciada.
- Request:
```json
{"token": "...", "new_password": "supersecret"}
```
- Validación: `new_password` mínimo 8 caracteres.
- Response: igual que `login`.

### `POST /v1/auth/password-reset/request`
- Auth: no
- Qué hace: genera un token de reset y lo envía por correo (adapter Resend). Responde igual exista o no el email, para no filtrar cuentas.
- Request: `{"email": "professional@acme.com"}`
- Response: `204 No Content`.

### `POST /v1/auth/password-reset/confirm`
- Auth: no
- Qué hace: consume el token de reset y fija la nueva contraseña.
- Request: `{"token": "...", "new_password": "supersecret"}`
- Response: `204 No Content`.

> `POST /v1/auth/register` ya no existe. El alta de profesionales es local (`make create-professional`,
> `make invite-professional`).

---

## Tenant

### `GET /v1/tenant/profile`
- Auth: sí (profesional)
- Response:
```json
{"tenant_id": "...", "name": "DrAcme", "professional_name": "Ana Rodríguez"}
```

### `PUT /v1/tenant/profile`
- Auth: sí (profesional)
- Request: `{"professional_name": "Ana Rodríguez"}`
- Response: igual que `GET`.

---

## Agent

### `GET /v1/agent/system-prompt`
- Auth: sí
- Qué hace: retorna el system prompt vigente del tenant. En la práctica es el XML generado a partir del
  perfil profesional; editarlo a mano se sobreescribe la próxima vez que se guarde el formulario.
- Response: `{"tenant_id": "...", "system_prompt": "..."}`

### `PUT /v1/agent/system-prompt`
- Auth: sí
- Request: `{"system_prompt": "..."}` (no puede ser vacío)
- Response: igual que `GET`.

### `GET /v1/agent/settings`
- Auth: sí
- Response:
```json
{
  "tenant_id": "...",
  "message_debounce_delay_seconds": 5,
  "assistant_enabled": true,
  "appointment_reminder_enabled": true,
  "appointment_reminder_days_before": 1,
  "appointment_reminder_attendance_template_name": "recordatorio_asistencia",
  "appointment_reminder_payment_template_name": "recordatorio_pago",
  "payment_details_text": null,
  "office_location": {"address": "Calle 1 #2-3", "arrival_instructions": "Torre B, piso 4"},
  "payment_timing": "BEFORE_SESSION"
}
```

### `PUT /v1/agent/settings`
- Auth: sí
- Request: mismo shape sin `tenant_id`.
- Validación:
  - `message_debounce_delay_seconds` entero entre 0 y 30.
  - `appointment_reminder_days_before` entre 1 y 7; requerido si `appointment_reminder_enabled`.
  - `appointment_reminder_attendance_template_name` requerido si `appointment_reminder_enabled`.
  - `payment_timing`: `"BEFORE_SESSION"` o `"AFTER_SESSION"`.
- Response: igual que `GET /v1/agent/settings`.

### `GET /v1/agent/professional-profile`
- Auth: sí
- Qué hace: retorna los campos estructurados del perfil profesional que alimentan el formulario de
  configuración y de los que se deriva el system prompt.
- Response:
```json
{
  "tenant_id": "...",
  "identity": {
    "assistant_name": "Claudia",
    "professional_title": "Dra.",
    "professional_name": "Ana Rodríguez",
    "professional_address_term": "la Doc",
    "main_city": "Cali",
    "tone": "Profesional y cálida.",
    "languages": ["español"]
  },
  "professional_context": {
    "approach": "Enfoque humanista.",
    "common_topics": ["ansiedad", "duelo"],
    "services_not_offered": ["terapia de pareja"],
    "coverage_notes": null
  },
  "services": [
    {
      "name": "Consulta Individual Adultos",
      "description": null,
      "modalities": ["PRESENCIAL", "VIRTUAL"],
      "target_patients": ["NEW", "RETURNING"],
      "enabled": true,
      "tariffs": [
        {
          "label": "Sesión individual",
          "description": null,
          "prices": [
            {"currency": "COP", "amount": 130000},
            {"currency": "USD", "amount": 90}
          ]
        }
      ]
    }
  ],
  "payment_methods": [
    {
      "currency": "COP",
      "method_name": "Nequi",
      "holder": "Ana Rodríguez",
      "instructions": "300 000 0000",
      "applies_when": "Colombia (COP)"
    }
  ]
}
```
- Si el tenant todavía no tiene perfil, devuelve `tenant_id` con campos en `null` o listas vacías.

### `PUT /v1/agent/professional-profile`
- Auth: sí
- Qué hace: actualiza los campos estructurados. Al guardar, el backend **regenera el XML del
  `system_prompt`** desde estos campos (`professional_profile_xml_renderer`) y lo persiste en
  `AgentProfile.system_prompt`. Los demás ajustes (`message_debounce_delay_seconds`, recordatorios,
  `office_location`, `payment_details_text`) se preservan.
- Request: mismo shape que la response sin `tenant_id`, más `payment_timing` opcional. Todos los campos son opcionales.
- Validación:
  - `modalities`: subset de `["PRESENCIAL", "VIRTUAL"]`.
  - `target_patients`: subset de `["NEW", "RETURNING"]` (default ambos).
  - `enabled`: permite apagar un servicio sin borrarlo (el bot deja de ofrecerlo).
  - `currency`: código de 3 letras (`COP`, `USD`, ...). Un mismo tarifario puede tener varias monedas en `prices`.
- Response: igual que `GET /v1/agent/professional-profile`.

> Nota de compatibilidad: el shape anterior (`audience`, `tariffs_local`/`tariffs_foreign`,
> `presencial_schedule`, `virtual_schedule`) ya no existe. Los horarios se resuelven contra la
> disponibilidad real de Google Calendar, no contra bloques declarados en el perfil.

---

## WhatsApp Onboarding

### `POST /v1/whatsapp/embedded-signup/session`
- Auth: sí
- Qué hace: crea estado de onboarding (`state`) y devuelve URL para iniciar Embedded Signup.
- Response:
```json
{"state": "...", "connect_url": "https://www.facebook.com/..."}
```

### `POST /v1/whatsapp/embedded-signup/complete`
- Auth: sí
- Qué hace: completa la conexión WhatsApp del tenant con `code` + `state`. Además suscribe la app al
  WABA (`POST /{WABA_ID}/subscribed_apps`) y registra el número (`POST /{PHONE_NUMBER_ID}/register`).
- Request: `{"code": "...", "state": "..."}`
- Response:
```json
{
  "tenant_id": "...",
  "status": "CONNECTED",
  "phone_number_id": "...",
  "business_account_id": "..."
}
```
- Nota local/dev: soporta `code` mock con formato `mock::<phone_number_id>::<business_account_id>::<access_token>`.

### `GET /v1/whatsapp/connection`
- Auth: sí
- Response:
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
- Qué hace: retorna el `verify_token` global de plataforma para configurar el webhook en Meta (uso dev).
- Response: `{"verify_token": "..."}`

---

## WhatsApp Templates

Plantillas arbitrarias del tenant en Meta.

### `GET /v1/whatsapp/templates`
- Auth: sí
- Response:
```json
{
  "templates": [
    {
      "id": "...",
      "name": "recordatorio_cita",
      "category": "UTILITY",
      "language": "es",
      "status": "APPROVED",
      "components": [
        {"type": "BODY", "text": "Hola {{1}}, te recordamos tu cita.", "example_values": ["Ana"]}
      ]
    }
  ]
}
```
- `status`: `APPROVED`, `PENDING`, `REJECTED`, `DISABLED`.

### `POST /v1/whatsapp/templates`
- Auth: sí
- Qué hace: crea la plantilla en Meta y la deja en revisión.
- Request:
```json
{
  "name": "recordatorio_cita",
  "category": "UTILITY",
  "language": "es",
  "components": [
    {"type": "BODY", "text": "Hola {{1}}, te recordamos tu cita.", "example_values": ["Ana"]}
  ]
}
```
- `category`: `MARKETING`, `UTILITY`, `AUTHENTICATION`.
- Response: objeto `TemplateDTO`.

### `DELETE /v1/whatsapp/templates/{template_name}`
- Auth: sí
- Response: `204 No Content`.

---

## Official Reminder Templates

Plantillas "oficiales" de la plataforma (texto controlado por el producto) que el tenant activa en su
propia cuenta de Meta. Son las que usan los recordatorios de asistencia y de pago.

### `GET /v1/whatsapp/templates/official/status`
- Auth: sí
- Response:
```json
{
  "items": [
    {
      "kind": "ATTENDANCE",
      "name": "aviso_cita_confirmada",
      "meta_status": "APPROVED",
      "rejection_reason": null
    }
  ]
}
```
- `meta_status`: `NOT_CREATED`, `PENDING`, `APPROVED`, `REJECTED`, `DISABLED`.
- Definiciones (nombre, idioma, categoría y cuerpo) en `src/domain/official_reminder_templates.py`:
  `ATTENDANCE` → `aviso_cita_confirmada`, `PAYMENT` → `aviso_pago_pendiente`.

### `POST /v1/whatsapp/templates/official/{kind}/activate`
- Auth: sí
- Qué hace: crea/envía a revisión la plantilla oficial del tipo indicado en la cuenta del tenant.
- `kind`: valores de `OfficialReminderKind` (`ATTENDANCE`, `PAYMENT`).
- Response: `OfficialTemplateStatusDTO`.

### `POST /v1/whatsapp/templates/official/{kind}/deactivate`
- Auth: sí
- Response: `204 No Content`.

---

## Webhooks (Meta)

### `GET /v1/webhooks/whatsapp`
- Auth: no (llamado por Meta)
- Qué hace: verificación inicial del webhook (`hub.challenge`).
- Query params: `hub.mode`, `hub.verify_token`, `hub.challenge`.
- Validación: `hub.verify_token` debe coincidir con `META_WEBHOOK_VERIFY_TOKEN`.
- Response: texto plano con `hub.challenge`.

### `POST /v1/webhooks/whatsapp`
- Auth: no (llamado por Meta)
- Qué hace:
  - resuelve tenant por `phone_number_id` y deduplica por `provider_event_id`
  - ignora números en blacklist
  - si el mensaje es echo de `OWNER_APP` (el profesional respondiendo desde su WhatsApp), lo guarda como `role=human_agent` y fuerza `control_mode=HUMAN`
  - si es `CUSTOMER` y la conversación está en modo `AI`, aplica debounce y ejecuta el `ConversationGraph`
  - envía la respuesta por WhatsApp, la persiste y marca el evento como procesado
- Request: payload oficial de Meta.
- Response: `{"status": "processed"}`
- Nota: solo procesa mensajes de tipo `text`.

---

## Conversations

### `GET /v1/conversations`
- Auth: sí
- Qué hace: lista conversaciones del tenant, ordenadas por `updated_at` descendente.
- Response:
```json
{
  "items": [
    {
      "conversation_id": "...",
      "whatsapp_user_id": "...",
      "contact_name": "Ana",
      "last_message_preview": "...",
      "updated_at": "2026-02-14T00:00:00Z",
      "control_mode": "AI",
      "tag_ids": ["tag-1"],
      "tags": [
        {
          "id": "tag-1",
          "tenant_id": "...",
          "name": "Primera vez",
          "slug": "primera-vez",
          "color": "#22C55E",
          "tag_type": "SYSTEM",
          "created_at": "2026-03-01T00:00:00Z",
          "updated_at": "2026-03-01T00:00:00Z"
        }
      ]
    }
  ]
}
```

### `GET /v1/conversations/{conversation_id}/messages`
- Auth: sí
- Response:
```json
{
  "items": [
    {
      "message_id": "...",
      "conversation_id": "...",
      "role": "user|assistant|system|human_agent",
      "direction": "INBOUND|OUTBOUND",
      "content": "...",
      "created_at": "2026-02-14T00:00:00Z"
    }
  ]
}
```

### `PUT /v1/conversations/{conversation_id}/control-mode`
- Auth: sí
- Request: `{"control_mode": "AI"}` (valores: `"AI"`, `"HUMAN"`)
- Response:
```json
{
  "conversation_id": "...",
  "tenant_id": "...",
  "control_mode": "AI",
  "updated_at": "2026-03-15T10:00:00Z"
}
```

### `POST /v1/conversations/{conversation_id}/messages`
- Auth: sí
- Qué hace: envía un mensaje del profesional al paciente por WhatsApp.
- Request: `{"message_text": "Hola, te confirmo la cita para mañana."}`
- Response: `201 Created`
```json
{
  "message_id": "...",
  "conversation_id": "...",
  "role": "assistant",
  "content": "Hola, te confirmo la cita para mañana.",
  "created_at": "2026-03-15T10:00:00Z"
}
```

### `DELETE /v1/conversations/{conversation_id}/messages`
- Auth: sí
- Qué hace: resetea el historial de mensajes de una conversación.
- Response: `204 No Content`.

---

## Tags

Etiquetas por conversación. Hay tags `SYSTEM` y `CUSTOM` (del profesional). Las `SYSTEM` se
auto-provisionan por tenant y espejan el estado de la scheduling request (`awaiting-consultation-review`,
`awaiting-consultation-details`, `awaiting-patient-choice`, `awaiting-payment-confirmation`,
`consultation-rejected`, `cancelled`, `booked`, `session-closed`, `human-handoff`); ver
`SYSTEM_TAG_DEFINITIONS` en `src/services/use_cases/tag_service.py`.

### `GET /v1/tags`
- Auth: sí
- Response: `{"items": [TagDTO, ...]}`

### `POST /v1/tags`
- Auth: sí
- Request: `{"name": "Urgente", "color": "#EF4444"}`
- Response: `TagDTO` (con `tag_type: "CUSTOM"`).

### `PUT /v1/tags/{tag_id}`
- Auth: sí
- Request: `{"name": "Urgente", "color": "#DC2626"}` (ambos opcionales)
- Response: `TagDTO`.

### `DELETE /v1/tags/{tag_id}`
- Auth: sí
- Response: `204 No Content`.

### `POST /v1/conversations/{conversation_id}/tags/{tag_id}`
- Auth: sí
- Qué hace: asigna un tag a una conversación.
- Response: `204 No Content`.

### `DELETE /v1/conversations/{conversation_id}/tags/{tag_id}`
- Auth: sí
- Qué hace: quita un tag de una conversación.
- Response: `204 No Content`.

---

## Events (SSE)

### `GET /v1/events`
- Auth: sí
- Qué hace: stream Server-Sent Events con cambios en tiempo real del tenant. El backend suscribe
  listeners de Firestore (`on_snapshot`) sobre conversaciones, scheduling requests y recordatorios.
- Response: `text/event-stream`. Headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- Eventos emitidos:
  - `connected` → `{"tenant_id": "..."}` (primer evento al abrir el stream)
  - `conversation.updated` → `{"id": "<conversation_id>"}`
  - `scheduling_request.updated` → `{"id": "<request_id>"}`
  - `reminder.updated` → `{"id": "<reminder_id>"}`
  - comentario `: keepalive` cada 25 segundos sin actividad
- El frontend lo usa como señal de realtime; el polling queda como red de seguridad.

---

## Patients

### `GET /v1/patients`
- Auth: sí (profesional)
- Qué hace: lista pacientes del tenant, ordenados por `created_at` descendente.
- Response:
```json
{
  "items": [
    {
      "tenant_id": "...",
      "whatsapp_user_id": "573001234567",
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "jane@example.com",
      "age": 29,
      "location": "Bogota",
      "phone_prefix": "+57",
      "phone": "573001234567",
      "created_at": "2026-03-02T00:44:28Z"
    }
  ]
}
```
- `phone_prefix` es `string | null`. El chatbot no lo captura por separado, así que los pacientes creados por el bot lo traen en `null`.

### `GET /v1/patients/{whatsapp_user_id}`
- Auth: sí (profesional)
- Response: `PatientDTO`.

### `POST /v1/patients`
- Auth: sí (profesional)
- Request: campos de `PatientDTO` sin `tenant_id` ni `created_at`.
- Response: `PatientDTO`.

### `PUT /v1/patients/{whatsapp_user_id}`
- Auth: sí (profesional)
- Request: mismos campos que `POST` sin `whatsapp_user_id`.
- Response: `PatientDTO`.

### `DELETE /v1/patients/{whatsapp_user_id}`
- Auth: sí (profesional)
- Response: `204 No Content`.

---

## Blacklist

### `GET /v1/blacklist`
- Auth: sí
- Response:
```json
{
  "items": [
    {"tenant_id": "...", "whatsapp_user_id": "573001234567", "created_at": "2026-03-15T10:00:00Z"}
  ]
}
```

### `POST /v1/blacklist`
- Auth: sí
- Request: `{"whatsapp_user_id": "573001234567"}` (upsert)
- Response: item de blacklist.

### `DELETE /v1/blacklist/{whatsapp_user_id}`
- Auth: sí
- Response: `204 No Content`.

---

## Google Calendar

### `POST /v1/google-calendar/oauth/session`
- Auth: sí
- Response: `{"state": "...", "connect_url": "https://accounts.google.com/o/oauth2/..."}`

### `POST /v1/google-calendar/oauth/complete`
- Auth: sí
- Request: `{"code": "...", "state": "..."}`
- Response:
```json
{
  "tenant_id": "...",
  "status": "CONNECTED",
  "calendar_id": "primary",
  "professional_timezone": "America/Bogota",
  "connected_at": "2026-03-15T10:00:00Z"
}
```

### `GET /v1/google-calendar/connection`
- Auth: sí
- Response: igual que `oauth/complete`. `status`: `"CONNECTED"` | `"DISCONNECTED"`.

### `GET /v1/google-calendar/availability`
- Auth: sí
- Query params: `from`, `to` (datetime ISO 8601, requeridos).
- Response:
```json
{
  "tenant_id": "...",
  "calendar_id": "primary",
  "timezone": "America/Bogota",
  "busy_intervals": [
    {"start_at": "2026-03-15T09:00:00-05:00", "end_at": "2026-03-15T10:00:00-05:00"}
  ]
}
```

---

## OAuth callbacks

### `GET /oauth/meta/callback`
- Auth: no (redirección de Meta)
- Qué hace: completa Embedded Signup usando `code` + `state` del query string.
- Comportamiento:
  - éxito: `303` a `FRONTEND_APP_BASE_URL/inbox?meta_oauth=connected`
  - error: `303` a `FRONTEND_APP_BASE_URL/onboarding/whatsapp?meta_oauth=error...`
  - fallback: HTML de éxito/error si `FRONTEND_APP_BASE_URL` está vacío
- Recomendado: configurar esta ruta como `META_REDIRECT_URI` en Meta.

### `GET /oauth/google/callback`
- Auth: no (redirección de Google)
- Qué hace: completa OAuth de Google Calendar usando `code` + `state`.
- Comportamiento:
  - éxito: `303` a `FRONTEND_APP_BASE_URL/inbox?google_oauth=connected`
  - error: `303` a `FRONTEND_APP_BASE_URL/onboarding/whatsapp?google_oauth=error&status=...&reason=...`
  - fallback: HTML si `FRONTEND_APP_BASE_URL` está vacío

---

## Onboarding

### `GET /v1/onboarding/status`
- Auth: sí
- Response:
```json
{
  "whatsapp_connected": true,
  "google_calendar_connected": false,
  "google_calendar_reauth_required": false,
  "ready": false
}
```
- `google_calendar_reauth_required`: hay conexión guardada pero Google rechazó el refresh
  (`invalid_grant`). La UI muestra un banner de reconexión en vez de dejar que los endpoints de
  Calendar fallen con `502` en cada poll.

---

## Manual Appointments

Citas creadas por el profesional desde el panel (no vienen del chatbot).

### `GET /v1/manual-appointments`
- Auth: sí
- Query params: `status` (opcional).
- Response:
```json
{
  "items": [
    {
      "appointment_id": "...",
      "tenant_id": "...",
      "patient_whatsapp_user_id": "573001234567",
      "status": "SCHEDULED",
      "calendar_event_id": "...",
      "start_at": "2026-03-20T09:00:00-05:00",
      "end_at": "2026-03-20T10:00:00-05:00",
      "timezone": "America/Bogota",
      "summary": "Consulta inicial",
      "is_virtual": true,
      "meet_url": "https://meet.google.com/abc-defg-hij",
      "payment_amount_cop": 150000,
      "payment_currency": "COP",
      "payment_method": "TRANSFER",
      "payment_status": "PENDING",
      "payment_updated_at": null,
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-15T10:00:00Z",
      "cancelled_at": null
    }
  ]
}
```
- `status`: `"SCHEDULED"` | `"CANCELLED"`.

### `POST /v1/manual-appointments`
- Auth: sí
- Qué hace: crea la cita y el evento en Google Calendar. El paciente recibe la invitación por correo
  desde la cuenta del profesional (`sendUpdates=all`). Si `is_virtual`, el evento incluye link de Meet.
- Request:
```json
{
  "patient_whatsapp_user_id": "573001234567",
  "start_at": "2026-03-20T09:00:00-05:00",
  "end_at": "2026-03-20T10:00:00-05:00",
  "timezone": "America/Bogota",
  "summary": "Consulta inicial",
  "is_virtual": true,
  "payment_amount_cop": 150000,
  "payment_currency": "COP",
  "payment_status": "PENDING",
  "payment_method": null
}
```
- Validación: `end_at > start_at`; `payment_amount_cop > 0`; `payment_method` requerido si `payment_status` es `"PAID"`.
- Response: objeto de cita completo.

### `PUT /v1/manual-appointments/{appointment_id}/reschedule`
- Auth: sí
- Request: `start_at`, `end_at`, `timezone`, `summary` (opcional).
- Response: objeto de cita actualizado.

### `DELETE /v1/manual-appointments/{appointment_id}`
- Auth: sí
- Request (opcional): `{"reason": "Paciente solicitó cancelar"}`
- Response: objeto de cita con `status: "CANCELLED"`.

### `PUT /v1/manual-appointments/{appointment_id}/payment`
- Auth: sí
- Request:
```json
{
  "payment_amount_cop": 150000,
  "payment_currency": "COP",
  "payment_method": "TRANSFER",
  "payment_status": "PAID"
}
```
- `payment_method`: `"CASH"` | `"TRANSFER"`. `payment_status`: `"PENDING"` | `"PAID"`.
- Response: objeto de cita actualizado.

### `POST /v1/manual-appointments/{appointment_id}/change-modality`
- Auth: sí
- Qué hace: cambia entre presencial y virtual. Al pasar a virtual se genera link de Meet en el evento;
  al pasar a presencial se quita.
- Request: `{"new_modality": "VIRTUAL"}`
- Response: objeto de cita actualizado.

---

## Scheduling Requests

Solicitudes de agendamiento originadas en el chatbot.

### `GET /v1/scheduling-requests`
- Auth: sí (profesional)
- Query params: `status` (opcional).
- Response:
```json
{
  "items": [
    {
      "request_id": "...",
      "conversation_id": "...",
      "whatsapp_user_id": "573001234567",
      "request_kind": "INITIAL",
      "status": "AWAITING_CONSULTATION_REVIEW",
      "round_number": 1,
      "patient_preference_note": null,
      "rejection_summary": null,
      "professional_note": null,
      "patient_first_name": "Jane",
      "patient_last_name": "Doe",
      "patient_age": 29,
      "consultation_reason": "Ansiedad",
      "consultation_details": null,
      "appointment_modality": "VIRTUAL",
      "patient_location": "Bogota",
      "slot_options_map": {},
      "selected_slot_id": null,
      "calendar_event_id": null,
      "payment_amount_cop": null,
      "payment_currency": "COP",
      "payment_method": null,
      "payment_status": "PENDING",
      "payment_updated_at": null,
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-15T10:00:00Z",
      "slots": [
        {
          "slot_id": "...",
          "start_at": "2026-03-20T09:00:00-05:00",
          "end_at": "2026-03-20T10:00:00-05:00",
          "timezone": "America/Bogota",
          "status": "AVAILABLE"
        }
      ]
    }
  ]
}
```
- `request_kind`: `"INITIAL"`, `"RETRY"`, `"RESCHEDULE"`.
- `status`: `AWAITING_CONSULTATION_REVIEW`, `AWAITING_CONSULTATION_DETAILS`, `AWAITING_PATIENT_CHOICE`,
  `AWAITING_PAYMENT_CONFIRMATION`, `AWAITING_ATTENDANCE_CONFIRMATION`, `CONSULTATION_REJECTED`,
  `CANCELLED`, `BOOKED`, `SESSION_CLOSED`, `HUMAN_HANDOFF`.

### `GET /v1/conversations/{conversation_id}/scheduling/requests`
- Auth: sí (profesional)
- Response: igual que `GET /v1/scheduling-requests`, filtrado por conversación.

### `POST /v1/conversations/{conversation_id}/scheduling/requests/{request_id}/consultation-review`
- Auth: sí
- Qué hace: el profesional revisa el motivo de consulta y decide.
- Request:
```json
{"decision": "REQUEST_MORE_INFO", "professional_note": "Necesito más detalle sobre los síntomas"}
```
- `decision`: `"REQUEST_MORE_INFO"` | `"REJECT"`.
- Response: `{"status": "...", "outbound_message_id": "...", "assistant_text": "..."}`

### `POST /v1/conversations/{conversation_id}/scheduling/requests/{request_id}/payment-review`
- Auth: sí
- Request:
```json
{
  "decision": "APPROVE",
  "professional_note": null,
  "payment_amount_cop": 150000,
  "payment_currency": "COP"
}
```
- `decision`: `"APPROVE"` | `"SEND_REMINDER"`. `payment_amount_cop` requerido (y > 0) si `APPROVE`.
- Response: igual shape que `consultation-review`.

### `POST /v1/conversations/{conversation_id}/scheduling/requests/{request_id}/professional-slots`
- Auth: sí
- Qué hace: el profesional propone horarios al paciente.
- Request:
```json
{
  "slots": [
    {
      "slot_id": "slot-1",
      "start_at": "2026-03-20T09:00:00-05:00",
      "end_at": "2026-03-20T10:00:00-05:00",
      "timezone": "America/Bogota"
    }
  ],
  "professional_note": "Estos son los horarios disponibles"
}
```
- Validación: al menos 1 slot, `end_at > start_at` en cada uno.
- Response:
```json
{
  "status": "AWAITING_PATIENT_CHOICE",
  "slot_batch_id": "...",
  "outbound_message_id": "...",
  "assistant_text": "..."
}
```

### `POST /v1/conversations/{conversation_id}/scheduling/close-session`
- Auth: sí (profesional)
- Qué hace: cierra manualmente la sesión de agendamiento activa de la conversación.
- Response: `{"status": "..."}`

### `PUT /v1/scheduling-requests/{request_id}/booked-slot/reschedule`
- Auth: sí (profesional)
- Request: `start_at`, `end_at`, `timezone`, `event_summary`.
- Response: `SchedulingRequestSummaryDTO`.

### `DELETE /v1/scheduling-requests/{request_id}/booked-slot`
- Auth: sí (profesional)
- Request (opcional): `{"reason": "Paciente solicitó cancelar"}`
- Response: `SchedulingRequestSummaryDTO`.

### `PUT /v1/scheduling-requests/{request_id}/booked-slot/payment`
- Auth: sí (profesional)
- Request:
```json
{
  "payment_amount_cop": 150000,
  "payment_currency": "COP",
  "payment_method": "TRANSFER",
  "payment_status": "PAID"
}
```
- Response: `SchedulingRequestSummaryDTO`.

### `POST /v1/scheduling-requests/{request_id}/booked-slot/change-modality`
- Auth: sí (profesional)
- Request: `{"new_modality": "PRESENCIAL"}`
- Response: `SchedulingRequestSummaryDTO`.

---

## Reminders

Recordatorios de cita programados (Cloud Tasks) que se envían por plantilla oficial de WhatsApp.

### `GET /v1/reminders`
- Auth: sí
- Query params: `status` (opcional).
- Response:
```json
{
  "items": [
    {
      "reminder_id": "...",
      "source_type": "MANUAL_APPOINTMENT",
      "source_id": "...",
      "patient_whatsapp_user_id": "573001234567",
      "patient_name": "Jane Doe",
      "appointment_start_at": "2026-03-20T09:00:00-05:00",
      "reminder_scheduled_for": "2026-03-19T09:00:00-05:00",
      "template_name": "aviso_cita_confirmada",
      "status": "PENDING",
      "failure_reason": null,
      "created_at": "2026-03-15T10:00:00Z"
    }
  ]
}
```
- `source_type`: `"SCHEDULING_REQUEST"` | `"MANUAL_APPOINTMENT"`.
- `status`: `"PENDING"` | `"SENT"` | `"FAILED"` | `"CANCELLED"`.

### `POST /v1/reminders/{reminder_id}/send-now`
- Auth: sí
- Qué hace: dispara el recordatorio inmediatamente, sin esperar la tarea programada.
- Response: `{"status": "..."}`

---

## Settings

### `GET /v1/settings/dev-features`
- Auth: sí (profesional)
- Qué hace: indica si la build expone features de desarrollo y el estado del modo sandbox.
- Response:
```json
{"enabled": true, "sandbox_enabled": false}
```
- Si `enable_dev_endpoints` es `false`, devuelve `{"enabled": false, "sandbox_enabled": null}`.

### `PUT /v1/settings/sandbox`
- Auth: sí (profesional). Requiere `enable_dev_endpoints`.
- Qué hace: activa/desactiva el modo sandbox (salidas de WhatsApp en no-op: nada sale a Meta).
- Request: `{"sandbox_enabled": true}`
- Response: `{"sandbox_enabled": true}`

---

## Internal (Cloud Tasks)

Endpoints llamados por Cloud Tasks, no por la UI. Reciben `tenant_id` en el body porque no hay JWT.

> Pendiente: validar el token OIDC del service account que invoca (hoy no se verifica identidad).

### `POST /v1/internal/scheduling-requests/{scheduling_request_id}/auto-close`
- Auth: no (tarea programada)
- Qué hace: cierra la sesión de una request que quedó en `BOOKED` (o en
  `AWAITING_ATTENDANCE_CONFIRMATION`) pasado el delay configurado.
- Request: `{"tenant_id": "..."}`
- Response: `{"status": "..."}`

### `POST /v1/internal/reminders/{reminder_id}/execute`
- Auth: no (tarea programada)
- Qué hace: envía el recordatorio por plantilla y pre-posiciona el estado de la conversación para
  poder interpretar la respuesta del paciente (ver "reminder-reply routing" en `BACKEND_CONTEXT.md`).
- Request: `{"tenant_id": "..."}`
- Response: `{"status": "..."}`

---

## Admin (`/v1/admin`)

Panel de soporte multi-tenant. **Todos** requieren rol admin (`require_admin_claims`) y escriben una
línea de auditoría en el logger `admin_audit` con `admin_user_id` + `tenant_id`.

Salvo el dashboard, cada endpoint es el equivalente "para un tenant arbitrario" de su versión de
profesional, con el mismo request/response body.

### Dashboard
- `GET /v1/admin/dashboard` → métricas globales:
```json
{
  "tenants_count": 12,
  "tenants_active": 9,
  "total_patients": 340,
  "total_conversations": 512,
  "total_manual_appointments_upcoming": 23,
  "total_pending_reminders": 8,
  "control_mode_distribution": {"AI": 480, "HUMAN": 32},
  "top_tenants_by_conversations": [TenantSummaryDTO, ...]
}
```
- `GET /v1/admin/tenants?search=` → `[TenantSummaryDTO]`
- `GET /v1/admin/tenants/{tenant_id}` → `TenantSummaryDTO` (`404` si no existe)

`TenantSummaryDTO`:
```json
{
  "tenant_id": "...",
  "tenant_name": "DrAcme",
  "professional_name": "Ana Rodríguez",
  "patient_count": 34,
  "conversation_count": 51,
  "active_conversations_today": 4,
  "manual_appointment_count_upcoming": 3,
  "pending_reminder_count": 1,
  "total_revenue_cop_this_month": 1800000,
  "last_activity_at": "2026-03-15T10:00:00Z",
  "owner_email": "professional@acme.com",
  "owner_is_active": true
}
```

### Pacientes
- `GET /v1/admin/tenants/{tenant_id}/patients?search=`
- `POST /v1/admin/tenants/{tenant_id}/patients` → `201`
- `GET /v1/admin/tenants/{tenant_id}/patients/{whatsapp_user_id}`
- `PUT /v1/admin/tenants/{tenant_id}/patients/{whatsapp_user_id}`
- `DELETE /v1/admin/tenants/{tenant_id}/patients/{whatsapp_user_id}` → `204`

### Conversaciones
- `GET /v1/admin/tenants/{tenant_id}/conversations`
- `GET /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/messages`
- `PUT /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/control-mode`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/messages` → `201`
- `DELETE /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/messages` → `204`
  (además requiere `enable_dev_endpoints`)

### Citas manuales
- `GET /v1/admin/tenants/{tenant_id}/manual-appointments?status=`
- `POST /v1/admin/tenants/{tenant_id}/manual-appointments` → `201`
- `PUT /v1/admin/tenants/{tenant_id}/manual-appointments/{appointment_id}/reschedule`
- `DELETE /v1/admin/tenants/{tenant_id}/manual-appointments/{appointment_id}`
- `PUT /v1/admin/tenants/{tenant_id}/manual-appointments/{appointment_id}/payment`
- `POST /v1/admin/tenants/{tenant_id}/manual-appointments/{appointment_id}/change-modality`

### Scheduling
- `GET /v1/admin/tenants/{tenant_id}/scheduling-requests?status=`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/consultation-review`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/payment-review`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/professional-slots`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/reschedule`
- `DELETE /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/booked-slot`
- `PUT /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/booked-payment`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/change-modality`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/close-session`
- `GET /v1/admin/tenants/{tenant_id}/scheduling/availability?from=&to=`

### Recordatorios
- `GET /v1/admin/tenants/{tenant_id}/reminders?status=`
- `POST /v1/admin/tenants/{tenant_id}/reminders/{reminder_id}/send-now`

### Tags
- `GET /v1/admin/tenants/{tenant_id}/tags`
- `POST /v1/admin/tenants/{tenant_id}/tags` → `201`
- `PUT /v1/admin/tenants/{tenant_id}/tags/{tag_id}`
- `DELETE /v1/admin/tenants/{tenant_id}/tags/{tag_id}` → `204`
- `POST /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/tags/{tag_id}` → `204`
- `DELETE /v1/admin/tenants/{tenant_id}/conversations/{conversation_id}/tags/{tag_id}` → `204`

### Blacklist
- `GET /v1/admin/tenants/{tenant_id}/blacklist`
- `POST /v1/admin/tenants/{tenant_id}/blacklist`
- `DELETE /v1/admin/tenants/{tenant_id}/blacklist/{whatsapp_user_id}` → `204`

### Configuración del agente
- `GET|PUT /v1/admin/tenants/{tenant_id}/agent/system-prompt`
- `GET|PUT /v1/admin/tenants/{tenant_id}/agent/settings`
- `GET|PUT /v1/admin/tenants/{tenant_id}/agent/professional-profile`

### Google Calendar
- `GET /v1/admin/tenants/{tenant_id}/google-calendar/connection`

---

## Dev (`/v1/dev`)

Solo se registran si `enable_dev_endpoints` es `true`.

### `POST /v1/dev/memory/reset`
- Auth: sí (JWT)
- Qué hace: limpia estado en Firestore (tenants, users, conversaciones, eventos, índices y refresh tokens).
- Response: `{"status": "reset"}`

### `POST /v1/dev/memory/chat/reset`
- Auth: sí (JWT)
- Qué hace: limpia solo estado de chat (conversaciones, mensajes, scheduling, blacklist, pacientes,
  deduplicación de eventos) sin borrar la configuración base del tenant.
- Response: `{"status": "chat_reset"}`

### `POST /v1/dev/eval-tenants`
- Auth: header `X-Eval-Admin-Secret` (comparado con `EVAL_ADMIN_SECRET`)
- Qué hace: crea un tenant efímero para una corrida de evaluación.
- Request: `{"run_id": "...", "shape_name": "shape_minimal"}`
- Response: `201` con `EvalTenantCreatedDTO`.

### `DELETE /v1/dev/eval-tenants/{tenant_id}`
- Auth: header `X-Eval-Admin-Secret`
- Response: `204 No Content`.

### `DELETE /v1/dev/eval-runs/{run_id}`
- Auth: sí (JWT de cualquier tenant logueado; **no** requiere el secret, porque se invoca desde el
  dashboard de evaluación autenticado)
- Qué hace: borra la corrida completa en cascada (todos sus shape docs + tenants efímeros).
- Response: `EvalRunDeleteStatsDTO`.

---

## Eval (`/v1/eval`)

Solo se registran si `eval_endpoints_enabled` es `true`. Alimentan el dashboard de evaluación del
frontend (`/evaluacion`).

### `GET /v1/eval/shapes`
- Auth: sí
- Qué hace: lista los shapes (perfiles profesionales sintéticos) de `tests/fixtures/profiles/*.json`.
- Response:
```json
{
  "items": [
    {
      "name": "shape_minimal",
      "description": "...",
      "required_combos": [["colombia", "nuevo_paciente"]],
      "rendered_system_prompt": "<identity>...</identity>"
    }
  ]
}
```

### `GET /v1/eval/personas`
- Auth: sí
- Response:
```json
{
  "items": [
    {
      "id": "persona_01",
      "display_name": "...",
      "capabilities": ["colombia", "nuevo_paciente"],
      "profile_group": "psicologa"
    }
  ]
}
```

### `GET /v1/eval/capabilities`
- Auth: sí
- Qué hace: catálogo de capabilities con su significado. `category` distingue identidad del paciente
  (`location`, `cohort`), lo que el paciente hace (`behavior`) y lo que el bot debe hacer bien
  (`bot_behavior`, verificado sobre los mensajes OUTBOUND).
- Response: `{"items": [{"id": "...", "description": "...", "implications": "...", "category": "behavior"}]}`

### `GET /v1/eval/prompt-versions`
- Auth: sí
- Response: `{"items": [{"id": "...", "label": "...", "active": true}]}`

### `GET /v1/eval/runs`
- Auth: sí
- Response: listado resumido de corridas:
```json
{
  "items": [
    {
      "run_doc_id": "...",
      "run_id": "...",
      "shape_name": "shape_minimal",
      "started_at": "2026-03-22T22:17:01Z",
      "finished_at": "2026-03-22T22:24:40Z",
      "total_personas": 6,
      "ok": 5,
      "fail": 1,
      "skipped": false
    }
  ]
}
```

### `GET /v1/eval/runs/{run_doc_id}`
- Auth: sí
- Qué hace: detalle de una corrida, con transcript por conversación y el veredicto del juez LLM por
  capability declarada.
- Response: `EvalRunDetailDTO` (incluye `uncovered_combos`, `eval_tenant_id` y
  `conversations[].judge_verdict` con `verifications[]` y `overall` en `all_verified|partial|none`).

---

## Flujo mínimo recomendado (manual)

1. `make create-professional EMAIL=... TENANT_NAME=...` (solo primera vez por ambiente)
2. `POST /v1/auth/login`
3. `POST /v1/whatsapp/embedded-signup/session`
4. `POST /v1/whatsapp/embedded-signup/complete`
5. `GET /v1/whatsapp/dev/verify-token` (solo dev; en producción usar `META_WEBHOOK_VERIFY_TOKEN`)
6. `GET /v1/whatsapp/connection`
7. `POST /v1/google-calendar/oauth/session` + `complete` (o `make oauth-flow`)
8. `PUT /v1/agent/professional-profile` (genera el system prompt)
9. Enviar mensaje de prueba en WhatsApp
10. `GET /v1/conversations` → `GET /v1/conversations/{conversation_id}/messages`
