# Agendachat

Agente conversacional de WhatsApp multi-tenant para agendamiento de citas: backend FastAPI con
arquitectura hexagonal, panel web en React y orquestación agéntica con LangGraph.

> Nota: el repo, los servicios Cloud Run, los buckets de GCS y los secrets siguen llamándose
> `ai-agent`/`ai-agent-backend`/`ai-agent-frontend`/etc. para no romper logs históricos, dashboards,
> alertas e integraciones de IAM/Secret Manager. **Agendachat es la marca pública** (dominio, copy de
> UI, paquetes); `ai-agent` es la identidad técnica interna.

> **dev activo desde 2026-08-01; prod hibernado.** Ver `docs/HIBERNATION.md` antes de desplegar.

## Documentación

| Documento | Contenido |
|-----------|-----------|
| `CLAUDE.md` | Guía global del repo: stack, capas, reglas de ingeniería, comandos |
| `docs/BACKEND_CONTEXT.md` | Arquitectura backend, módulo agéntico, flujos, adapters |
| `docs/API_ENDPOINTS.md` | Referencia de todos los endpoints con schemas |
| `docs/PROMPTS_CONTEXT.md` | Sistema de prompts, estados, tools, reglas de estilo |
| `docs/FRONTEND_PLAN.md` | Rutas, estructura hexagonal y realtime del panel web |
| `docs/DEPLOYMENT.md` | Deploy de infra y código (dev/prod) |
| `docs/HIBERNATION.md` | Qué se destruyó al pausar el proyecto y cómo restaurar |
| `docs/MANUAL_SETUP_DEV_ENV.md` | Setup manual del ambiente dev en GCP |
| `docs/TECH_DEBT.md` | Deuda técnica priorizada |
| `docs/archive/META_BACKEND_E2E_README.md` | Onboarding de Meta y ciclo de vida del mensaje (E2E) |

## Qué hace

- Atiende WhatsApp por tenant vía Meta Cloud API y responde con Gemini (Vertex AI) usando function calling.
- Lleva el flujo de agendamiento completo: motivo de consulta → revisión del profesional → propuesta de
  horarios → selección → pago → reserva en Google Calendar → recordatorio → confirmación de asistencia.
- Permite reprogramar y cancelar, y pasar la conversación a modo humano cuando hace falta.
- Panel web con inbox, agenda, clientes, finanzas, recordatorios y configuración del asistente.
- Panel de administración multi-tenant y dashboard de evaluación automatizada del bot.

## Stack

- Backend: FastAPI + arquitectura hexagonal + Firestore + Gemini (Vertex AI) + LangGraph
- Frontend: React + Vite + TypeScript estricto + Tailwind + TanStack Query
- Infra: GCP (Cloud Run, Artifact Registry, Secret Manager, Cloud Tasks), Terraform
- Tooling: `uv`, `ruff`, `mypy`, `bandit`, `pre-commit`

## Quick start

```bash
uv sync --group dev
uv run pre-commit install
uv run uvicorn src.entrypoints.web.main:app --reload
```

Frontend (otra terminal):

```bash
make fe-install
make fe-dev
```

El estado de dominio vive en Firestore y toda la configuración de runtime se lee de Secret Manager.
Setup local requerido:

```bash
gcloud auth application-default login
gcloud config set project your_gcp_project_id
```

Si corres local con credenciales ADC en JSON:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your/adc.json
```

## Gestión de profesionales

Cada profesional es un tenant independiente. La gestión es local, por comandos de Make (requiere acceso a GCP):

```bash
make create-professional EMAIL=doc@acme.com TENANT_NAME=DrAcme
make invite-professional EMAIL=doc@acme.com TENANT_NAME=DrAcme   # alta por email de invitación
make list-professionals
make reset-password EMAIL=doc@acme.com
make delete-professional EMAIL=doc@acme.com
make oauth-flow                                                   # conectar Google Calendar
```

`create-professional` genera una contraseña aleatoria y la imprime. Las credenciales quedan en
`.secrets/` para uso de los demás comandos.

## Correr con Docker

```bash
make docker-up-build
```

URLs:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

En Docker local, el CORS del backend se puede sobrescribir con `CORS_ALLOWED_ORIGINS_OVERRIDE`
(lista separada por comas). Para detener: `make docker-down`.

## Checks

```bash
make static-checks   # ruff + mypy + bandit
make fe-checks       # lint + format + typecheck + test del frontend
make checks          # todo
```

Backend tests:

```bash
uv run pytest tests/services -q   # suite objetivo del día a día
uv run pytest                     # suite completa
```

## Simular un mensaje entrante de WhatsApp (dev)

```bash
make simulate-whatsapp-message MESSAGE="Hola, necesito una cita"
```

Variables opcionales: `SIM_WA_USER_ID` (default `573001234567`), `SIM_WA_USER_NAME`
(default `Cliente Demo`), `SIM_PROVIDER_MESSAGE_ID` (default autogenerado).

## Evaluación automatizada del bot

```bash
make eval-list                              # lista los shapes disponibles
make eval                                   # corre todos los shapes
make eval SHAPES="shape_minimal"            # filtra a uno o varios shapes
make eval-no-cleanup                        # deja vivos los tenants efímeros para inspeccionar
```

Los targets de eval usan la variable `EVAL_ADC` del Makefile como
`GOOGLE_APPLICATION_CREDENTIALS`; hoy apunta a una ruta local fija, así que hay que ajustarla al
entorno propio antes de correrlos.

Cada shape es un perfil profesional sintético (`tests/fixtures/profiles/*.json`). El runner crea un
tenant efímero, corre conversaciones con personas simuladas y un juez LLM verifica las capabilities
declaradas. Los resultados se ven en `/evaluacion` del panel. Detalle en `docs/BACKEND_CONTEXT.md`.

## Configuración runtime (Secret Manager)

El backend carga toda su configuración del secret `AI_AGENT_APP_CONFIG_JSON` al arrancar: `JWT_SECRET`,
`META_*`, `GEMINI_*`, credenciales de Google OAuth, CORS, URLs, límites y toggles.

```bash
make app-config-secret-upsert ENV=prod APP_CONFIG_PAIR='META_REDIRECT_URI:https://tu-dominio/oauth/meta/callback'
make app-config-secret-sync-env ENV=prod APP_CONFIG_ENV_FILE=.env
```

Ver `docs/DEPLOYMENT.md` para las variantes (valores tipados, upsert múltiple, prune del `.env`).

## Deploy

```bash
make deploy-back ENV=prod   # backend + SPA en la misma imagen
```

La SPA se compila en la primera etapa de `Dockerfile.backend` y la sirve FastAPI, así que no hay
deploy de frontend separado ni load balancer: la app vive en la URL de Cloud Run.

El deploy automático a dev corre en `push` a `develop` vía GitHub OIDC + Workload Identity Federation
(sin JSON keys). Detalles de workflows, secrets por ambiente y módulos Terraform en
`docs/DEPLOYMENT.md` y `docs/MANUAL_SETUP_DEV_ENV.md`.

## Logging

Logs JSON estructurados a `stdout` con correlación por request:
- Se reutiliza el `X-Request-ID` entrante; si no llega, se genera.
- Toda respuesta HTTP incluye el header `X-Request-ID`.
- Las excepciones no controladas devuelven `500` con
  `{"detail":"internal server error","request_id":"<id>"}`; el traceback solo va al log del servidor.

Config (dentro de `AI_AGENT_APP_CONFIG_JSON`): `LOG_LEVEL` (default `INFO`),
`LOG_INCLUDE_REQUEST_SUMMARY` (default `false`).

## Landing para revisión de Meta (deploy aparte)

Los estáticos viven en `landing/` (`index.html`, `privacy.html`, `terms.html`, `styles.css`). Se
despliegan como sitio estático bajo HTTPS y esas URLs se usan en el perfil de Meta Business y el flujo
de revisión.
