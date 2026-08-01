# Deuda Tecnica

Auditoria pre-produccion (2026-03-28). Ultima revision: 2026-08-01 (pasada de sincronizacion doc/codigo).
Prioridades: **BLOQUEANTE** (resolver antes de prod), **IMPORTANTE** (resolver en sprint post-launch), **BACKLOG**.

> Convenciones de estado:
> - **RESUELTO** + commit/PR: verificado en `develop` HEAD.
> - **EN VUELO**: PR abierto que cierra el item pero aun no mergeado a `develop`.
> - **REVISAR**: el item puede estar parcialmente resuelto o el contexto cambio; alguien tiene que volver a chequear con la nota indicada.
> - sin marca: sigue abierto, no hay trabajo en curso.

---

## BLOQUEANTE

_Todos los items originales de esta seccion ya estan **RESUELTOS** o tienen un fix **EN VUELO**. Mantenidos como historico hasta que se decida archivar la seccion._

### 1. Sin separacion de ambientes en Terraform

**RESUELTO** en `51f40dc` (`feat: separate dev/prod environments for Terraform and CI/CD`). Hay `envs/{dev,prod}.tfvars` por modulo y el workflow de GitHub Actions resuelve `environment` desde push (dev) vs `workflow_dispatch` (dev/prod selector). Secrets viven en GitHub Environments scoped por ambiente.

---

### 2. State management local sin locking

**RESUELTO** en `51f40dc`. Backend ahora es `gcs` (ver `infra/terraform/runtime_deploy/versions.tf:4`) con prefijos por ambiente. Make targets locales solo despliegan a dev.

---

### 3. Sin health checks en Cloud Run

**RESUELTO (con caveat)** en `326f00e` (`feat: phase 2 prod hardening — healthz, rate limiting, error boundaries`). Se agrego `/readyz` con check de Firestore y timeout de 1.5s (ver `src/entrypoints/web/routers/health_router.py`). El endpoint `/healthz` sigue siendo "shallow ok" para liveness ligero — esto es deliberado.

**REVISAR (sigue abierto):** `google_cloud_run_v2_service` no declara `startup_probe` ni `liveness_probe` apuntando a `/readyz` (verificado en `infra/terraform/runtime_deploy/main.tf`). Validar si Cloud Run los necesita explicitos o si el routing por defecto hacia `/` es suficiente para nuestro uso.

---

### 4. `min_instances = 0` en produccion

**RESUELTO** en `51f40dc`. `infra/terraform/runtime_deploy/envs/prod.tfvars:5` define `min_instances = 1`; dev queda en 0 para ahorro.

---

### 5. Sin rate limiting en webhooks ni endpoints de auth

**RESUELTO** en `326f00e`. Se introdujo `slowapi` (ver `src/entrypoints/web/rate_limiter.py`) con limites en auth (5/min login, 10/min refresh/logout) y webhook (30/min verify, 120/min receive). Toggle por `rate_limit_enabled` para tests.

---

### 6. Sesiones BOOKED nunca se auto-cierran

**RESUELTO** en `fef1d79` (`feat: auto-close BOOKED sessions via Cloud Tasks after 1 hour`). `SchedulingService.auto_close_booked_request` cierra la sesion via tarea programada en la Cloud Tasks queue provista por Terraform (`cloud_tasks_queue_name`, default `scheduling-tasks`; la misma cola despacha los recordatorios).

---

### 7. Sin Error Boundaries en React

**RESUELTO** en `326f00e`. `frontend/src/adapters/inbound/react/components/ErrorBoundary.tsx` envuelve el `AppRouter` con fallback en castellano (`ErrorFallback.tsx`).

---

## IMPORTANTE

### 8. Sin monitoring ni alerting

**Problema:**
No hay Cloud Monitoring alerts configurados. Si el servicio tiene errores 5xx sostenidos, latencia alta, o instancias reiniciandose, nadie se entera hasta que un usuario reporta.

**Solucion propuesta:**
- Alertas basicas: tasa de errores 5xx > 5%, latencia p95 > 3s, instancia restarts.
- Canal de notificacion: email o Slack.
- Dashboard basico en Cloud Monitoring.

---

### 9. Sin smoke tests post-deploy ni rollback automatico

**Problema:**
Si `terraform apply` pasa pero el servicio no arranca correctamente, no hay validacion automatica ni rollback a la revision anterior de Cloud Run.

**Solucion propuesta:**
- `curl` a `/healthz` post-deploy en CI.
- Si falla, rollback automatico a revision anterior via `gcloud run services update-traffic`.

---

### 10. Valores hardcoded en Makefile y CI

**RESUELTO** en `51f40dc`. Project ID, scaling y region viven en `infra/terraform/runtime_deploy/envs/{dev,prod}.tfvars` y en GitHub Environments. CI calcula los nombres a partir de tfvars (ver workflow paso `Deploy backend`).

---

### 11. `except Exception` generico en servicios criticos

**RESUELTO (en lo critico).** Ya no quedan `except Exception` en `webhook_service.py` ni en
`cloud_tasks_adapter.py`. Los 4 sitios que sobreviven son deliberados y estan acotados:

- `src/adapters/outbound/langsmith/langsmith_tracer_adapter.py:137,191` — el tracing nunca debe tumbar una request.
- `src/entrypoints/web/lifespan.py:27` — cierre best-effort del cliente Firestore; una lifespan no puede propagar.
- `src/entrypoints/web/routers/health_router.py:54` — cualquier fallo del check debe traducirse a `degraded`, no a `500`.

Los tres loguean el error. No queda accion pendiente salvo que aparezcan sitios nuevos.

---

### 12. Sin graceful shutdown

**RESUELTO** en `86666a7` (`feat(infra): add FastAPI lifespan for graceful Firestore client shutdown`).
`src/entrypoints/web/lifespan.py` cierra el cliente de Firestore en el shutdown para que las conexiones
drenen cuando Cloud Run manda SIGTERM. Cubierto por `tests/entrypoints/web/test_main_lifespan.py`.

---

### 13. Webhook payload sin validacion Pydantic

**Archivo:** `src/entrypoints/web/routers/webhook_router.py:36`

**Problema:**
El endpoint sigue recibiendo `payload: dict[str, object]` sin validacion en la capa HTTP. Payloads
malformados llegan al service layer.

**Solucion propuesta:**
Definir DTO Pydantic para el payload de WhatsApp webhook o al menos validar estructura basica antes de delegar.

---

### 14. Sin tests de integracion HTTP

**Problema:**
Originalmente solo habia tests de capa de servicio. Coverage de routers via `TestClient` era cero.

**Estado:** **PARCIAL**. En `tests/entrypoints/web/` hay tests con `TestClient` para `admin_router`,
`auth_router`, `tenant_router`, `eval_router`, `dev_router_eval_runs`, `dev_router_eval_tenants`, mas
`test_main_lifespan`. Falta cobertura HTTP para `webhook_router`, `health_router`, `scheduling_router`,
`manual_appointment_router`, `conversation_router`, `events_router` y `internal_router`.

**Solucion propuesta:**
Agregar tests de integracion para los routers restantes, priorizando webhook, health e internal
(los tres son superficie no autenticada o semi-autenticada).

---

### 15. Validacion de forms minima en frontend

**Archivos:** `frontend/src/adapters/inbound/react/pages/LoginPage.tsx`, `AgendaPage.tsx`

**Problema:**
Solo HTML5 `required`/`minLength`. Sin validacion de formato de email, rangos de fecha, ni montos en formularios de pago.

**Solucion propuesta:**
Agregar `zod` con validacion en submit antes de llamar a la API.

---

### 16. Gaps de accesibilidad en frontend

**Problema:**
- Tabs sin `role="tab"` ni `aria-selected`.
- Botones de icono sin `aria-label`.
- Error banners sin `role="alert"`.
- Modales sin `role="dialog"`.

**Estado:** **REVISAR**. Hay componentes con `aria-label`, `role="dialog"`, `aria-selected`, `aria-labelledby` aplicados (`AppointmentDrawer`, `AppShell`, `BillingDisclosureModal`, `PatientCombobox`, `AppointmentDetailCard`, `SettingsSidebar`, `AuthShared`). Pasada original parcialmente hecha.

**Solucion propuesta:**
Auditar componentes de tabs e ErrorBanner que aun no tengan `role`/`aria-*`. Definir el alcance "minimo aceptable" para cerrar este item.

---

## BACKLOG

### 17. Sin lifecycle policy en Artifact Registry

Imagenes Docker se acumulan indefinidamente. Agregar policy de retencion (e.g., keep last 10) via `cleanup_policies` en `google_artifact_registry_repository`.

### 18. Dockerfile: build-essential no se remueve post-build

Imagen incluye compilador C innecesario. Multi-stage build o `apt remove` post-install.

### 19. Sin secret rotation policy

Secrets en Secret Manager no tienen rotacion automatica. Definir lifecycle rules.

### 20. Mensaje de pago hardcodeado en guards

**RESUELTO** en `7e7c50c` (`feat: slot picker UI, sandbox toggle, guard elimination, prompt refinements`). Se elimino `build_payment_instructions_message` de `src/services/agentic/guards/helpers.py`; el mensaje de pago se delega al LLM usando `<pricing>` del system prompt.

### 21. Terraform sobreescribe secret con version bootstrap

**RESUELTO** en `ada355e` (se removio el bootstrap automatico). Secret se gestiona manualmente via `make app-config-secret-upsert`. Mantener vigilancia para que no reaparezca.

### 22. Endpoints `/v1/internal/**` sin validacion de identidad

**Archivo:** `src/entrypoints/web/routers/internal_router.py:20` (hay un `TODO` en el codigo)

Los dos endpoints que invoca Cloud Tasks (`auto-close` y `execute` de recordatorios) reciben el
`tenant_id` en el body y no validan el token OIDC del service account que los llama. Cualquiera que
alcance la URL de Cloud Run puede cerrar sesiones o disparar recordatorios de un tenant arbitrario.
Validar el OIDC token (issuer, audience y email del SA) antes de ejecutar.

### 23. Codigo muerto en `agentic/guards/`

`waiting_patient_choice_guard.py`, `numeric_slot_selection_guard.py` y
`waiting_professional_override_guard.py` no estan wired en el container, no aparecen en el
`ConversationGraph` y nada los importa. `ToolDefinitionRegistry.build_waiting_state_tool_definitions()`
solo lo usa uno de esos guards muertos. Decidir si se borran o si hay intencion de reactivarlos.

### 24. `AnthropicLlmProviderAdapter` sin wiring

`src/adapters/outbound/llm_anthropic/anthropic_llm_provider_adapter.py` implementa `LlmProviderPort`
pero el container solo instancia el adapter de Gemini y no hay setting para elegir provider. O se
expone la seleccion por configuracion, o se retira.

### 25. `AgentProfile.identity.timezone` se pierde al guardar el perfil

La entidad tiene el campo y lo usan `RuntimeContextSection` (formato de `fecha_cita`) y
`ReminderService` (programacion de recordatorios), pero `AssistantIdentityDTO` no lo expone y
`agent_service._identity_dto_to_entity()` no lo copia. Guardar el formulario lo deja en `None` y todo
cae al fallback `America/Bogota`. Impacta a cualquier tenant fuera de esa zona horaria.

---

## Resuelto (historico breve)

- ~~Sin graceful shutdown~~ -> `86666a7`. Lifespan de FastAPI que cierra el cliente de Firestore.
- ~~`except Exception` generico en servicios criticos~~ -> los sitios criticos ya estan tipados; los 4 restantes son deliberados (tracing, lifespan, health check).
- ~~Terraform sobreescribe secret con version bootstrap~~ -> `ada355e`. Solo se gestiona via `gcloud`/Make.
- ~~Mensaje de pago hardcodeado en guards~~ -> `7e7c50c`. Lo genera el LLM via `<pricing>`.
- ~~Sesiones BOOKED nunca se auto-cierran~~ -> `fef1d79`. Cloud Tasks queue `scheduling-tasks`.
- ~~Sin separacion de ambientes en Terraform / state local sin locking / hardcoded values~~ -> `51f40dc`. Tfvars por ambiente, GCS backend, GitHub Environments.
- ~~Sin Error Boundaries / sin rate limiting / `/healthz` shallow~~ -> `326f00e`. ErrorBoundary, slowapi, `/readyz` con check Firestore.
