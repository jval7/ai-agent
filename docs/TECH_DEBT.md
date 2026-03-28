# Deuda Tecnica

Auditoria pre-produccion (2026-03-28).
Prioridades: **BLOQUEANTE** (resolver antes de prod), **IMPORTANTE** (resolver en sprint post-launch), **BACKLOG**.

---

## BLOQUEANTE

### 1. Sin separacion de ambientes en Terraform

**Archivos:** `infra/terraform/`, `Makefile`, `.github/workflows/deploy-main.yml`

**Problema:**
No hay workspaces ni tfvars por ambiente. Un solo state file cubre todo. Un `terraform apply` de dev puede pisar recursos de prod. No hay pipeline separado para dev vs prod en CI/CD (push a `main` despliega directo a produccion sin validacion intermedia).

**Solucion propuesta:**
- Crear `dev.tfvars` y `prod.tfvars` con valores especificos por ambiente.
- Usar GCS backend con prefijos por ambiente (`state/dev/`, `state/prod/`).
- Separar jobs en GitHub Actions: dev auto-deploy en push a `main`, prod manual o tag-based.

**Impacto:** Critico. Prerequisito para lanzar un ambiente dev sin riesgo para prod.

---

### 2. State management local sin locking

**Archivos:** `Makefile` (deploy targets), `.make-flow/deploy/state/*.tfstate`

**Problema:**
Deploys locales usan backend `local` sin mecanismo de locking. Deploys concurrentes (dos terminales, CI + local) pueden corromper el state. El state local puede contener secrets y no esta en `.gitignore` de forma explicita. CI usa GCS pero sin validacion de que el bucket exista.

**Solucion propuesta:**
- Mover todo state a GCS con locking nativo.
- Eliminar state local del flujo.
- Agregar `.make-flow/` a `.gitignore` si no esta.

**Impacto:** Critico. Corrupcion de state = deploy roto y posible perdida de recursos.

---

### 3. Sin health checks en Cloud Run

**Archivos:** `infra/terraform/runtime_deploy/`, `src/entrypoints/web/routers/health_router.py`

**Problema:**
- El recurso `google_cloud_run_v2_service` no define `startup_check` ni `liveness_check`.
- El endpoint `/healthz` retorna `{"status": "ok"}` sin verificar dependencias (Firestore, Secret Manager, auth de GCP).
- Cloud Run routea trafico a instancias que arrancan pero no pueden acceder a la DB.

**Solucion propuesta:**
- Agregar `startup_check` y `liveness_check` en Terraform apuntando a `/healthz`.
- Enriquecer `/healthz` para verificar conectividad a Firestore (lectura liviana).
- Considerar `/readyz` separado para checks mas completos.

**Impacto:** Critico. Usuarios reciben errores 500 si la instancia esta rota pero Cloud Run la considera healthy.

---

### 4. `min_instances = 0` en produccion

**Archivos:** `Makefile:482`, `.github/workflows/deploy-main.yml:104`

**Problema:**
Cold starts en cada periodo de inactividad. Para una API user-facing con WhatsApp webhooks que requieren respuesta rapida, esto causa latencia inaceptable (5-15s en primer request).

**Solucion propuesta:**
- `min_instances = 1` en prod.
- `min_instances = 0` en dev (ahorro de costos).
- Parametrizar via tfvars por ambiente.

**Impacto:** Critico para UX. Pacientes esperan >10s la primera respuesta del bot.

---

### 5. Sin rate limiting en webhooks ni endpoints de auth

**Archivos:** `src/entrypoints/web/routers/webhook_router.py`, `src/entrypoints/web/routers/auth_router.py`

**Problema:**
No hay rate limiting a nivel de aplicacion. El webhook de WhatsApp (`POST /v1/webhooks/whatsapp`) puede ser floodeado, escalando costos de Firestore y Vertex AI. Los endpoints de auth (`/login`, `/refresh`) son vulnerables a brute force.

**Solucion propuesta:**
- Agregar `slowapi` o middleware custom con limites por IP.
- Webhook: ~100 req/min por IP.
- Auth: ~10 intentos/min por IP en login, ~30/min en refresh.
- Alternativa: configurar rate limiting en Cloud Run ingress o un load balancer.

**Impacto:** Alto. Riesgo de abuso, costos descontrolados, y brute force en auth.

---

### 6. Sesiones BOOKED nunca se auto-cierran

**Archivo:** `src/services/use_cases/scheduling_service.py:1040-1043`

**Problema:**
Despues de booking exitoso, si el paciente no responde al "algo mas?", la sesion queda en estado `BOOKED` / `POST_BOOKING_FOLLOWUP` indefinidamente. Estado fantasma que se acumula.

**Solucion propuesta:**
Implementar Cloud Scheduler + endpoint que cierre sesiones inactivas tras 5 min en `POST_BOOKING_FOLLOWUP`.

**Impacto:** Medio-alto en prod con volumen real. Sesiones acumuladas pueden causar comportamiento impredecible.

---

### 7. Sin Error Boundaries en React

**Archivos:** `frontend/src/adapters/inbound/react/`

**Problema:**
No hay React Error Boundaries. Un error de runtime en cualquier componente crashea toda la app (pantalla blanca). El usuario pierde todo contexto sin feedback.

**Solucion propuesta:**
- Error boundary a nivel root (en `Providers.tsx` o `App.tsx`) con fallback UI.
- Error boundary a nivel de pagina para aislar fallos por seccion.

**Impacto:** Alto. En prod, un edge case en un componente tumba toda la app.

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

**Archivos:** `Makefile:43-56,482`, `.github/workflows/deploy-main.yml:101-108`

**Problema:**
Project ID, dominio, parametros de scaling (`max_instances=10`, `memory=512Mi`, `cpu=1`) estan hardcoded. Impide multi-ambiente sin duplicar codigo.

**Solucion propuesta:**
Extraer a tfvars por ambiente. CI lee variables de environment secrets de GitHub.

---

### 11. `except Exception` generico en servicios criticos

**Archivos:** `src/services/use_cases/webhook_service.py:699`, `src/infra/langsmith_tracer.py:129,183`

**Problema:**
Catching `Exception` base swallows errores inesperados silenciosamente. En webhook_service, un fallo al marcar evento como error se traga sin re-raise.

**Solucion propuesta:**
Capturar excepciones especificas (`GoogleAPICallError`, `ConnectionError`, etc.). Re-raise o log con nivel ERROR para excepciones inesperadas.

---

### 12. Sin graceful shutdown

**Archivos:** `src/entrypoints/web/main.py`

**Problema:**
No hay lifecycle hooks en FastAPI. El Firestore client no se cierra explicitamente. Requests in-flight se terminan abruptamente en deploys.

**Solucion propuesta:**
Usar lifespan context manager de FastAPI para cleanup de Firestore client y otros recursos.

---

### 13. Webhook payload sin validacion Pydantic

**Archivo:** `src/entrypoints/web/routers/webhook_router.py:27-31`

**Problema:**
El endpoint recibe `dict[str, object]` sin validacion en la capa HTTP. Payloads malformados llegan al service layer.

**Solucion propuesta:**
Definir DTO Pydantic para el payload de WhatsApp webhook o al menos validar estructura basica antes de delegar.

---

### 14. Sin tests de integracion HTTP

**Problema:**
Solo hay tests de capa de servicio (34 archivos). No hay tests con `TestClient` de FastAPI que validen routers, auth middleware, serialization de responses, ni manejo de errores HTTP.

**Solucion propuesta:**
Agregar tests de integracion para endpoints criticos: webhook, auth, health.

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

**Solucion propuesta:**
Pasar por cada componente interactivo y agregar atributos ARIA basicos.

---

## BACKLOG

### 17. Sin lifecycle policy en Artifact Registry

Imagenes Docker se acumulan indefinidamente. Agregar policy de retencion (e.g., keep last 10).

### 18. Dockerfile: build-essential no se remueve post-build

Imagen incluye compilador C innecesario. Multi-stage build o `apt remove` post-install.

### 19. Sin secret rotation policy

Secrets en Secret Manager no tienen rotacion automatica. Definir lifecycle rules.

### 20. Mensaje de pago hardcodeado en guards

**Archivo:** `src/services/agentic/guards/helpers.py` -> `build_payment_instructions_message()`

Precios COP hardcodeados en Python. No considera USD para extranjeros ni permite cambio sin tocar codigo. Bloquea multi-tenant. Solucion: delegar generacion del mensaje al LLM usando `<pricing>` del system prompt.

### 21. Terraform sobreescribe secret con version bootstrap

**Estado:** Parcialmente resuelto en commit `ada355e` (se removio el bootstrap automatico). Monitorear que no reaparezca. Secret se gestiona manualmente via `make app-config-secret-upsert`.

---

## Resuelto

- ~~Terraform sobreescribe secret con version bootstrap~~ -> Resuelto en `ada355e`. Ahora solo se gestiona via `gcloud`/Make.
