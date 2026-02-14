# Meta + Backend E2E (MVP)

Este documento resume el flujo real desde que una empresa autoriza Meta hasta que el agente responde en WhatsApp.

## 1) Setup de plataforma (una sola vez)

En Meta configuras:

- OAuth redirect: `META_REDIRECT_URI` (ejemplo: `https://<dominio>/oauth/meta/callback`)
- Webhook callback: `https://<dominio>/v1/webhooks/whatsapp`
- Webhook verify token: `META_WEBHOOK_VERIFY_TOKEN`
- Campo suscrito: `messages`

En backend (`.env`):

- `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`
- `META_WEBHOOK_VERIFY_TOKEN`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_API_VERSION`, `ANTHROPIC_MAX_TOKENS`

## 2) Onboarding de un tenant (empresa cliente)

1. El tenant autenticado llama `POST /v1/whatsapp/embedded-signup/session`.
2. Backend genera `state`, lo guarda como `embedded_signup_state` y retorna `connect_url`.
3. La empresa abre `connect_url`, inicia sesión en Meta y da permisos.
4. Meta redirige a `GET /oauth/meta/callback?code=...&state=...`.
5. Backend valida `state`, intercambia `code` por credenciales y obtiene:
   - `phone_number_id`
   - `business_account_id` (WABA)
   - `access_token`
6. Backend marca conexión del tenant como `CONNECTED`.

Clave multi-tenant: cada tenant queda mapeado por su `phone_number_id`.

## 3) Mensaje inbound y respuesta outbound

1. Un usuario final escribe al número de WhatsApp Business de la empresa.
2. Meta envía `POST /v1/webhooks/whatsapp`.
3. Backend parsea `metadata.phone_number_id` y resuelve el tenant.
4. Crea/recupera `WhatsappUser` + `Conversation`.
5. Guarda mensaje inbound.
6. Arma contexto: `system_prompt` del tenant + últimos N mensajes.
7. Llama Anthropic (`LlmProviderPort.generate_reply`).
8. Envía respuesta por Meta `/{phone_number_id}/messages`.
9. Guarda mensaje outbound y marca `provider_event_id` como procesado (dedupe).

## 4) IDs importantes (y para qué sirve cada uno)

- `state`: correlación y seguridad OAuth (evita cerrar sesiones incorrectas).
- `code`: token temporal de OAuth que se intercambia por acceso.
- `META_WEBHOOK_VERIFY_TOKEN`: verificación inicial del webhook (plataforma, no por tenant).
- `phone_number_id`: llave de ruteo multi-tenant en cada webhook inbound.
- `provider_event_id`: idempotencia/dedupe para no procesar doble.

## 5) Checks rápidos de operación

- Estado conexión tenant: `GET /v1/whatsapp/connection`
- Prompt activo tenant: `GET /v1/agent/system-prompt`
- Conversaciones: `GET /v1/conversations`
- Historial: `GET /v1/conversations/{conversation_id}/messages`

Si `phone_number_id` no está mapeado a un tenant, el evento inbound se ignora.
