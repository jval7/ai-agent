# Investigación: redirect_uri en Embedded Signup con FB JS SDK

## Contexto

Al migrar el WhatsApp onboarding de OAuth redirect a Facebook JS SDK (`FB.login()` con popup), el code exchange falla con:

```
Error validating verification code. Please make sure your redirect_uri
is identical to the one you used in the OAuth dialog request
(OAuthException, code=100, error_subcode=36008)
```

## El problema

Cuando `FB.login()` abre el popup de OAuth, el SDK internamente construye la URL con un `redirect_uri` que apunta a:

```
https://staticxx.facebook.com/x/connect/xd_arbiter/?version=46#cb=<HASH_DINAMICO>&domain=alejaescobar.com&...
```

Este `redirect_uri` es **interno de Facebook** y tiene un hash dinámico que cambia en cada sesión. Meta exige que el code exchange use exactamente el mismo `redirect_uri`, pero no tenemos forma de replicarlo.

## Lo que probamos

| Intento | redirect_uri en el exchange | Resultado |
|---------|---------------------------|-----------|
| 1 | Sin redirect_uri (omitido) | Error 36008: "redirect_uri is identical to..." |
| 2 | `https://alejaescobar.com` (origin) | Error 36008: "redirect_uri is identical to..." |
| 3 | `https://alejaescobar.com/configuraciones` (page URL / fallback_redirect_uri) | Error 36008: "redirect_uri is identical to..." |
| 4 | `https://staticxx.facebook.com/x/connect/xd_arbiter/` (base xd_arbiter) | Error 191: "domain not in app domains" |
| 5 | `https://staticxx.facebook.com/x/connect/xd_arbiter/?version=46` (xd_arbiter + query) | Pendiente de prueba |
| 6 | Capturar URL via `window.open` interceptor | No capturó la URL real (SDK no usa window.open para la URL interna) |

## Otras variaciones probadas

| Variación | Resultado |
|-----------|-----------|
| GET vs POST para el exchange | Mismo error con ambos |
| API version v23.0 vs v21.0 | Mismo error con ambas versiones |
| accessToken directo (sin response_type: 'code') | El config_id siempre retorna code, no accessToken |

## Documentación oficial consultada

### Implementación del Embedded Signup
- URL: `developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/implementation`
- Dice: el code se intercambia "después de registrar al cliente comercial"
- Apunta a dos flujos: "socio de soluciones" y "proveedor de tecnología"

### Registro como proveedor de tecnología
- URL: `developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-customers-as-a-tech-provider`
- Muestra el exchange SIN redirect_uri:
  ```
  curl --get 'https://graph.facebook.com/v21.0/oauth/access_token' \
    -d 'client_id=<APP_ID>' \
    -d 'client_secret=<APP_SECRET>' \
    -d 'code=<CODE>'
  ```
- Esto NO funciona para nuestra app (error 36008)

### Bird API Docs (tercero)
- URL: `docs.bird.com/.../setting-up-the-whatsapp-embedded-flow`
- Confirma: exchange solo con `client_id`, `client_secret`, `code` — sin `redirect_uri`

### Tokens de larga duración
- URL: `developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/`
- Flujo de "obtener código para clientes": SÍ requiere redirect_uri
- Flujo de "intercambiar token corto por largo": usa `grant_type=fb_exchange_token`

### SammyK Blog
- URL: `sammyk.me/best-practice-for-facebook-login-with-the-javascript-sdk-and-php-sdk-v4-1`
- Dice: cuando usas JS SDK, NO intercambias code server-side — extraes el token de la cookie del SDK directamente

## Hallazgos clave

1. **La config_id creada desde plantilla (60 días)** siempre retorna `code` en `authResponse.code`, nunca `accessToken`
2. **El FB SDK popup** usa internamente `xd_arbiter` como redirect_uri con hash dinámico
3. **La doc de tech provider** muestra exchange sin redirect_uri, pero solo funciona para proveedores/socios registrados
4. **Nuestra app no es** ni socio de soluciones ni proveedor de tecnología

## Opciones pendientes de explorar

1. **Registrarse como proveedor de tecnología** en Meta — puede habilitar el exchange sin redirect_uri
2. **Crear config_id custom** (no desde plantilla) que retorne accessToken directo en vez de code
3. **Usar la cookie del SDK** (`fbsr_{app_id}`) para obtener el token server-side sin exchange
4. **Volver al flujo OAuth redirect** y agregar coexistencia de otra forma
5. **Probar con `redirect_uri` = xd_arbiter con query params** (intento 5 pendiente)

## Config actual de Meta Developer Portal

- App ID: `1417232356372969`
- Config ID: `790106844174382` (plantilla "WhatsApp Embedded Signup 60 días")
- JS SDK habilitado: Sí
- Dominio frontend: `alejaescobar.com` (en App Domains y Allowed Domains for JS SDK)
- OAuth Redirect URIs: `https://ai-agent-backend-...run.app/oauth/meta/callback`, `https://alejaescobar.com`, `https://alejaescobar.com/configuraciones`
- App publicada: Sí
