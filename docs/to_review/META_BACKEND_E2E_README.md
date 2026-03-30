# Meta + Backend E2E (MVP)

Este documento resume el flujo real desde que una empresa autoriza Meta hasta que el agente responde en WhatsApp.

## 1) Setup de plataforma (una sola vez)

### 1.1) Meta Developer Portal

En tu app de Meta (`developers.facebook.com`):

1. **Inicio de sesión con Facebook para empresas > Configurar:**
   - Activar "Iniciar sesión con el SDK para JavaScript": **Sí**
   - Agregar dominio del frontend a "Dominios permitidos para el SDK para JavaScript" (ej: `https://alejaescobar.com`)
   - Agregar redirect URI en "URI de redireccionamiento de OAuth válidos" (ej: `https://<backend>/oauth/meta/callback`)
   - Activar "Aplicar HTTPS": **Sí**

2. **Inicio de sesión con Facebook para empresas > Configuraciones:**
   - Crear configuración desde plantilla: "Configuración de registro insertado de WhatsApp con un token que caduca en 60 días"
   - Copiar el `config_id` generado (se usa como `META_CONFIG_ID`)

3. **Casos de uso > WhatsApp > Configuración:**
   - Webhook URL: `https://<backend>/v1/webhooks/whatsapp`
   - Webhook verify token: valor de `META_WEBHOOK_VERIFY_TOKEN`
   - Suscribir campo: `messages`

4. **Publicar:**
   - La app debe estar **publicada** para recibir webhooks reales (no solo de prueba)

### 1.2) GCP Secret Manager

Secrets requeridos en `AI_AGENT_APP_CONFIG_JSON`:

| Key | Descripción |
|-----|-------------|
| `META_APP_ID` | App ID de Meta |
| `META_APP_SECRET` | App Secret de Meta |
| `META_CONFIG_ID` | Config ID del Embedded Signup (paso 1.1.2) |
| `META_REDIRECT_URI` | URI del callback OAuth del backend |
| `META_WEBHOOK_VERIFY_TOKEN` | Token de verificación del webhook |
| `META_API_VERSION` | Versión de la Graph API (ej: `v23.0`) |

Comando para agregar/actualizar un secret:
```bash
make app-config-secret-upsert APP_CONFIG_PAIR='META_CONFIG_ID:<valor>'
```

## 2) Onboarding de un tenant (empresa cliente)

### Flujo con Facebook JS SDK (coexistencia)

1. El tenant autenticado hace clic en "Conectar con Meta" en la UI.
2. Frontend llama `POST /v1/whatsapp/embedded-signup/session` → obtiene `{state, app_id, config_id}`.
3. Frontend carga el Facebook JS SDK con `app_id`.
4. Frontend ejecuta `FB.login()` con:
   - `config_id`: el ID de la configuración creada en Meta
   - `response_type: "code"`
   - `extras.featureType: "whatsapp_business_app_onboarding"` (habilita coexistencia)
   - `extras.sessionInfoVersion: "3"`
5. Se abre popup de Meta donde el usuario:
   - Inicia sesión con Facebook
   - Selecciona "Connect your existing WhatsApp Business App" (coexistencia)
   - Escanea QR code desde su app de WhatsApp Business
   - Autoriza permisos
6. El callback de `FB.login()` devuelve `authResponse.code`.
7. Frontend envía `POST /v1/whatsapp/embedded-signup/complete {code, state}`.
8. Backend intercambia `code` por credenciales:
   - `access_token`
   - `phone_number_id`
   - `business_account_id` (WABA)
9. Backend suscribe la app a la WABA: `POST /{WABA_ID}/subscribed_apps`.
10. Backend intenta registrar el número: `POST /{PHONE_NUMBER_ID}/register`.
    - Para cuentas SMB (coexistencia), este paso se omite automáticamente.
11. Backend marca la conexión del tenant como `CONNECTED`.

Clave multi-tenant: cada tenant queda mapeado por su `phone_number_id`.

### Coexistencia

Con el modo coexistencia (`featureType: whatsapp_business_app_onboarding`):
- El usuario **sigue usando la app de WhatsApp Business** en su teléfono.
- Los mensajes se **sincronizan** entre la app y el Cloud API.
- El chatbot responde via Cloud API y la respuesta aparece también en la app móvil.
- No necesita desconectar ni migrar su número.

## 3) Mensaje inbound y respuesta outbound

1. Un usuario final escribe al número de WhatsApp Business de la empresa.
2. Meta envía `POST /v1/webhooks/whatsapp`.
3. Backend parsea `metadata.phone_number_id` y resuelve el tenant.
4. Crea/recupera `WhatsappUser` + `Conversation`.
5. Guarda mensaje inbound.
6. Arma contexto: `system_prompt` del tenant + últimos N mensajes.
7. Llama Gemini (`LlmProviderPort.generate_reply`).
8. Envía respuesta por Meta `/{phone_number_id}/messages`.
9. Guarda mensaje outbound y marca `provider_event_id` como procesado (dedupe).

## 4) IDs importantes (y para qué sirve cada uno)

| ID | Propósito |
|----|-----------|
| `state` | Correlación y seguridad OAuth (CSRF) |
| `code` | Token temporal de OAuth que se intercambia por `access_token` |
| `config_id` | ID de la configuración de Facebook Login for Business (Embedded Signup) |
| `META_WEBHOOK_VERIFY_TOKEN` | Verificación inicial del webhook (global, no por tenant) |
| `phone_number_id` | Llave de ruteo multi-tenant en cada webhook inbound |
| `provider_event_id` | Idempotencia/dedupe para no procesar doble |

## 5) Checks rápidos de operación

- Estado conexión tenant: `GET /v1/whatsapp/connection`
- Prompt activo tenant: `GET /v1/agent/system-prompt`
- Conversaciones: `GET /v1/conversations`
- Historial: `GET /v1/conversations/{conversation_id}/messages`

Si `phone_number_id` no está mapeado a un tenant, el evento inbound se ignora.

## 6) Diferencia entre pasos Meta clave

| Paso | Qué hace |
|------|----------|
| `FB.login()` (Embedded Signup) | Popup donde el usuario autoriza, selecciona WABA y conecta su número. Retorna `code`. |
| `exchange_code_for_credentials` | Backend intercambia `code` por `access_token`, resuelve `WABA_ID` y `phone_number_id`. |
| `subscribed_apps` | Habilita entrega de webhooks inbound de esa WABA a tu app. |
| `register` | Activa el número para Cloud API (se omite para SMB/coexistencia). |

## 7) Troubleshooting

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| `(#200) Permissions error` en subscribe | El usuario no tiene permisos sobre el WABA | Verificar rol del usuario en Meta (debe ser admin o developer de la app) |
| `Register endpoint is not available for SMB` | Cuenta SMB, no necesita registro | Se omite automáticamente |
| Webhook no llega | App no publicada o webhook no configurado | Publicar app en Meta + verificar URL y suscripción a `messages` |
| `redirect_uri_mismatch` (Google Calendar) | URI en secrets no coincide con Google Console | Sincronizar `GOOGLE_OAUTH_REDIRECT_URI` con la configuración en Google Cloud Console |
| Popup bloqueado | Browser bloquea popup de FB.login() | El usuario debe permitir popups para el dominio del frontend |
