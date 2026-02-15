# Frontend Plan (MVP, guiado por capturas)

## Objetivo
Construir una UI operativa para el backend multi-tenant de WhatsApp, iterando diseño por screenshots y feedback textual (sin dependencia de Figma).

## Stack cerrado
- React + Vite
- TypeScript estricto
- Arquitectura hexagonal
- Tailwind + componentes headless
- TanStack Query
- Vitest + Testing Library + MSW
- ESLint + Prettier
- Seguridad frontend: `eslint-plugin-security` + `npm audit`

## Rutas iniciales
- `/login`
- `/register`
- `/onboarding/whatsapp`
- `/inbox`
- `/agent/prompt`

## Flujo de trabajo visual
1. Tú compartes captura + cambio esperado.
2. Se implementa en código la iteración.
3. Se reportan paths editados y resultado esperado.
4. Repetimos hasta cerrar pantalla.

## Orden de construcción
1. Auth (login/register).
2. Onboarding (estado + conectar Meta).
3. Inbox (conversaciones + mensajes).
4. Control (AI/HUMAN + blacklist).
5. Prompt (get/update system prompt).

## Estructura hexagonal de frontend
- `frontend/src/domain`
- `frontend/src/application`
- `frontend/src/ports`
- `frontend/src/adapters/inbound/react`
- `frontend/src/adapters/outbound/http`
- `frontend/src/adapters/outbound/storage`
- `frontend/src/infrastructure`
- `frontend/src/shared`

## Sesión y seguridad
- `access_token` en memoria.
- `refresh_token` en `localStorage` (`AI_AGENT_REFRESH_TOKEN`).
- Renovación automática de access token al recibir 401.

## Comandos
- `make fe-install`
- `make fe-dev`
- `make fe-checks`
- `make checks` (backend + frontend)
