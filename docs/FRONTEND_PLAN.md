# Frontend Context

Panel web de Agendachat: operación diaria del profesional (inbox, agenda, clientes, finanzas,
recordatorios, configuración), panel de administración multi-tenant y dashboard de evaluación.

## Stack
- React 18 + Vite 6
- TypeScript estricto
- Arquitectura hexagonal
- Tailwind + Radix (`@radix-ui/react-switch`)
- TanStack Query
- Luxon para fechas/timezones
- `@microsoft/fetch-event-source` para el stream SSE (permite mandar el header `Authorization`)
- Vitest + Testing Library + MSW
- ESLint + Prettier
- Seguridad: `eslint-plugin-security` + `npm audit`

## Rutas (`adapters/inbound/react/app/Router.tsx`)

### Públicas (`PublicOnlyRoute`)
- `/` — LandingPage
- `/roadmap` — RoadmapPage
- `/login` — LoginPage (registro deshabilitado)
- `/accept-invite` — AcceptInvitePage (alta por invitación)
- `/forgot-password` — ForgotPasswordPage
- `/reset-password` — ResetPasswordPage

### Profesional (`ProtectedRoute`)
- `/configuraciones` — ConfiguracionesPage (onboarding WhatsApp + Google Calendar + perfil profesional + settings + recordatorios)
- `/evaluacion` — EvaluacionPage (tabs: Shapes, Personas, Capabilities, Runs)
- `/evaluacion/runs/:runDocId` — RunDetailPage (transcripts + veredicto del juez)

### Profesional con onboarding completo (`ProtectedRoute` + `OnboardingReadyRoute`)
- `/inbox` — InboxPage
- `/agenda` — AgendaPage
- `/clientes` — ClientsPage
- `/finanzas` — FinanzasPage
- `/recordatorios` — RecordatoriosPage

### Admin (`AdminRoute`)
- `/admin` — AdminHomePage
- `/admin/dashboard` — AdminGlobalDashboardPage
- `/admin/tenants/:tenantId` y `/admin/tenants/:tenantId/:tab` — AdminTenantDetailPage

### Redirects legacy
- `/onboarding`, `/onboarding/whatsapp`, `/agent/prompt` → `/configuraciones`
- `/plantillas` → `/configuraciones?tab=recordatorios`
- `*` → `/configuraciones`

## Estructura hexagonal

```
frontend/src/
├── domain/models          # tipos de dominio
├── application/use_cases  # casos de uso (agent, auth, blacklist, conversation, evaluation,
│                          # manual_appointment, onboarding, patient, reminder, scheduling,
│                          # tenant, whatsapp_onboarding, whatsapp_template)
├── ports                  # backend_api_port, event_stream_port, token_session_port
├── adapters/
│   ├── inbound/react/     # app (Router + guards), pages, views, components, hooks, styles
│   └── outbound/
│       ├── http/          # backend_api_adapter, backend_event_stream_adapter
│       └── storage/       # browser_token_session_adapter
├── infrastructure/        # config + di
└── shared/                # facebook (SDK Embedded Signup), hooks, http, testing, utils
```

Convención de páginas: `pages/*Page.tsx` resuelve routing/estado de alto nivel y delega el render a
`pages/views/*View.tsx` (`AgendaView`, `InboxView`, `ClientsView`, `FinanzasView`,
`RecordatoriosView`, `ConfiguracionesView`). Las páginas grandes se apoyan en hooks dedicados
(`useAgendaQuery`, `useAgendaActions`, `useInboxQuery`, `useFinanzasQuery`, `useRemindersQuery`,
`usePatientsQuery`, `useBookedAppointments`, `useReschedule`, `useAgentSettingsQuery`).

## Realtime

- `useEventStream` se conecta a `GET /v1/events` vía `BackendEventStreamAdapter`.
- Eventos manejados: `connected`, `conversation.updated`, `scheduling_request.updated`, `reminder.updated`.
- Al recibir un evento se invalidan las queries de TanStack Query correspondientes.
- El polling queda como red de seguridad (~30s), no como mecanismo principal.
- Si el stream responde `401`/`403`, se corta sin reintentar (error fatal de auth).

## Sesión y seguridad
- `access_token` en memoria.
- `refresh_token` en `localStorage` bajo la clave `AI_AGENT_REFRESH_TOKEN`.
- Renovación automática del access token al recibir `401`.
- El rol se resuelve con `GET /v1/auth/me`; `AdminRoute` exige rol `admin`.
- `OnboardingReadyRoute` bloquea las vistas operativas hasta que `GET /v1/onboarding/status` devuelve `ready`.

## Comandos
Ver "Comandos útiles" en `CLAUDE.md` (fuente canónica). Adicionales: `make fe-install`,
`make fe-lint`, `make fe-typecheck`, `make fe-test`, `make fe-format`, `make fe-security`.
