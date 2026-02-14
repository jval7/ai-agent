# Frontend Plan (MVP)

## Objetivo
Construir una UI mínima para operar el agente de WhatsApp mientras backend ya está funcional.

## Alcance MVP de frontend
1. Autenticación:
- Login (`/v1/auth/login`)
- Registro (`/v1/auth/register`)
- Refresh token (`/v1/auth/refresh`)

2. Configuración del agente:
- Ver y editar system prompt (`GET/PUT /v1/agent/system-prompt`)

3. Conexión WhatsApp:
- Iniciar Embedded Signup (`POST /v1/whatsapp/embedded-signup/session`)
- Completar callback OAuth automáticamente (ruta backend ya existe)
- Ver estado conexión (`GET /v1/whatsapp/connection`)

4. Operación de conversaciones:
- Lista de conversaciones (`GET /v1/conversations`)
- Historial por conversación (`GET /v1/conversations/{id}/messages`)
- Cambiar control mode AI/HUMAN (`PUT /v1/conversations/{id}/control-mode`)

5. Blacklist:
- Listar (`GET /v1/blacklist`)
- Agregar (`POST /v1/blacklist`)
- Eliminar (`DELETE /v1/blacklist/{whatsapp_user_id}`)

## Pantallas recomendadas (orden)
1. `Auth` (login + register)
2. `Onboarding WhatsApp` (estado + conectar)
3. `Inbox` (lista conversaciones + detalle mensajes)
4. `Control Panel` (switch AI/HUMAN + blacklist)
5. `Agent Prompt` (configuración prompt)

## Estructura sugerida de frontend
- `src/app` o `src/pages`: pantallas.
- `src/components`: UI reutilizable (inputs, botones, tabla, badges).
- `src/features/auth`
- `src/features/onboarding`
- `src/features/conversations`
- `src/features/blacklist`
- `src/features/agent`
- `src/lib/api`: cliente HTTP + manejo de tokens.

## Contrato mínimo de UX
- Estados por vista: loading, empty, error, success.
- Mensajes de error claros para:
  - credenciales inválidas,
  - conexión Meta incompleta,
  - proveedor externo caído (`502`),
  - token expirado (`401`).
- Toda acción sensible debe tener feedback visible (toast/banner/inline).

## Seguridad de sesión (MVP)
- `access_token`: usar en header Bearer.
- `refresh_token`: renovar sesión al expirar access.
- Si refresh falla: cerrar sesión local y redirigir a login.

## Plan por fases
1. Fase 1: Auth + layout base + cliente API.
2. Fase 2: Conexión WhatsApp + estado.
3. Fase 3: Inbox conversaciones + historial.
4. Fase 4: control AI/HUMAN + blacklist.
5. Fase 5: pulido de UX y hardening de errores.

## Definiciones pendientes (decidir antes de codificar)
- Framework: React+Vite o Next.js.
- Librería UI: Tailwind + componentes propios o kit externo.
- Manejo estado remoto: fetch simple o React Query.
- Estrategia de storage de tokens (memoria/localStorage/cookie).
