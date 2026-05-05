# Setup de App de Meta para WhatsApp Embedded Signup

Checklist para configurar una nueva app de Meta que soporte el flujo de Embedded Signup con coexistencia.

## Prerequisitos

- [ ] Portafolio comercial (Business Portfolio) creado y verificado
- [ ] App de Meta creada con caso de uso "WhatsApp Business"
- [ ] App asociada al portafolio comercial verificado

## Paso 1: Configuración básica de la app

En **Configuración de la app > Básica**:

- [ ] Nombre visible configurado
- [ ] URL de política de privacidad configurada
- [ ] Dominio del frontend agregado en "Dominios de la app" (ej: `alejaescobar.com`)
- [ ] Categoría seleccionada

## Paso 2: Configuración de OAuth

En **Inicio de sesión con Facebook para empresas > Configurar**:

- [ ] "Inicio de sesión del cliente de OAuth": **Sí**
- [ ] "Inicio de sesión de OAuth web": **Sí**
- [ ] "Aplicar HTTPS": **Sí**
- [ ] "Iniciar sesión con el SDK para JavaScript": **Sí**
- [ ] "Usar modo estricto para URI de redireccionamiento": **Sí**
- [ ] URI de redireccionamiento de OAuth válidos:
  - `https://<backend>/oauth/meta/callback` (para flujo redirect)
  - `https://<frontend-domain>` (para flujo JS SDK)
  - `https://<frontend-domain>/configuraciones` (para flujo JS SDK)
- [ ] Dominios permitidos para el SDK para JavaScript: `https://<frontend-domain>`

## Paso 3: Crear configuración de Embedded Signup (config_id)

En **Inicio de sesión con Facebook para empresas > Configuraciones**:

- [ ] Crear desde plantilla: "Configuración de registro insertado de WhatsApp con un token que caduca en 60 días"
- [ ] Copiar el `config_id` generado
- [ ] Guardar como `META_CONFIG_ID` en GCP Secret Manager

## Paso 4: Configurar Webhook

En **Casos de uso > WhatsApp > Configuración**:

- [ ] URL de webhook: `https://<backend>/v1/webhooks/whatsapp`
- [ ] Token de verificación: valor de `META_WEBHOOK_VERIFY_TOKEN`
- [ ] Suscribir campo: `messages`

## Paso 5: Publicar la app

- [ ] Ir a **Publicar** y publicar la app (requerido para recibir webhooks reales)

## Paso 6: Roles

- [ ] Usuarios de prueba agregados como **Desarrollador** (no Evaluador) en **Roles de la app > Roles**

## Implementación del Embedded Signup (6 pasos de la doc oficial)

Referencia: [Implementación del registro insertado](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/implementation)

### 1. Cargar el SDK de Facebook

```html
<script async defer crossorigin="anonymous" src="https://connect.facebook.net/en_US/sdk.js"></script>
```

### 2. Inicializar el SDK

```javascript
window.fbAsyncInit = function () {
  FB.init({
    appId: '<APP_ID>',
    autoLogAppEvents: true,
    xfbml: true,
    version: '<GRAPH_API_VERSION>'
  });
};
```

### 3. Función de escucha de eventos (sessionInfoListener)

Escucha eventos `postMessage` de Facebook para capturar `phone_number_id`, `waba_id` y `business_id` del popup.

```javascript
window.addEventListener('message', (event) => {
  if (!event.origin.endsWith('facebook.com')) return;
  try {
    const data = JSON.parse(event.data);
    if (data.type === 'WA_EMBEDDED_SIGNUP') {
      // data.data contiene: phone_number_id, waba_id, business_id
      // data.event contiene: FINISH, FINISH_ONLY_WABA, o CANCEL
    }
  } catch { }
});
```

### 4. Devolución de llamada de respuesta (callback)

Captura el `code` del `response.authResponse.code` de `FB.login()`.

```javascript
const fbLoginCallback = (response) => {
  if (response.authResponse) {
    const code = response.authResponse.code;
    // Enviar code al backend para intercambio
  }
};
```

### 5. Método de inicio (FB.login)

```javascript
FB.login(fbLoginCallback, {
  config_id: '<CONFIGURATION_ID>',
  response_type: 'code',
  override_default_response_type: true,
  extras: {
    setup: {},
    featureType: 'whatsapp_business_app_onboarding',  // SOLO para coexistencia
    sessionInfoVersion: '3'
  }
});
```

Nota: `featureType: 'whatsapp_business_app_onboarding'` habilita coexistencia (requiere ser Tech Provider).

### 6. Registrar clientes comerciales (code exchange)

Intercambiar el `code` por un `access_token` server-side:

```bash
curl --get 'https://graph.facebook.com/v21.0/oauth/access_token' \
  -d 'client_id=<APP_ID>' \
  -d 'client_secret=<APP_SECRET>' \
  -d 'code=<CODE>'
```

Nota: este exchange sin `redirect_uri` solo funciona para **Tech Providers** o **Socios de Soluciones**. Sin ese rol, el exchange falla con error 36008.

## Secrets en GCP (por ambiente)

```bash
make app-config-secret-upsert-many ENV=prod APP_CONFIG_PAIRS='\
  META_APP_ID:<valor> \
  META_APP_SECRET:<valor> \
  META_CONFIG_ID:<valor> \
  META_WEBHOOK_VERIFY_TOKEN:<valor>'
```

| Key | Descripción |
|-----|-------------|
| `META_APP_ID` | App ID de Meta |
| `META_APP_SECRET` | App Secret de Meta |
| `META_CONFIG_ID` | Config ID del Embedded Signup (paso 3) |
| `META_REDIRECT_URI` | URI del callback OAuth del backend |
| `META_WEBHOOK_VERIFY_TOKEN` | Token de verificación del webhook |
| `META_API_VERSION` | Versión de la Graph API (default: `v23.0`) |

## Flujos soportados

### Flujo A: OAuth Redirect (funciona sin ser Tech Provider)

```
Frontend → POST /embedded-signup/session → obtiene connect_url
Frontend → window.location.assign(connect_url) → redirect a Meta
Meta → GET /oauth/meta/callback?code=...&state=...
Backend → exchange code con redirect_uri → access_token
Backend → subscribe_app_to_waba + finalize
```

Limitación: no soporta coexistencia. El usuario debe desconectar la app de WhatsApp Business del teléfono.

### Flujo B: JS SDK con coexistencia (requiere Tech Provider)

```
Frontend → POST /embedded-signup/session → obtiene state, app_id, config_id
Frontend → FB.login() popup con featureType coexistence
Frontend → sessionInfoListener captura phone_number_id, waba_id
Frontend → POST /embedded-signup/complete {code, state, phone_number_id, waba_id}
Backend → exchange code sin redirect_uri → access_token
Backend → subscribe_app_to_waba + finalize
```

## Registro como Tech Provider

Referencia: [Convertirse en proveedor de tecnología](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers)

1. Verificación del negocio (ya completada)
2. Revisión de la app:
   - Configuración básica (ícono, privacidad, categoría)
   - 2 videos:
     - Video 1: mensaje enviado desde tu app y recibido en WhatsApp
     - Video 2: creación de plantilla (puede ser desde el admin de WhatsApp de Meta)
   - Solicitar Advanced Access para `whatsapp_business_messaging` y `whatsapp_business_management`
3. Tiempo estimado de aprobación: 1-4 semanas
