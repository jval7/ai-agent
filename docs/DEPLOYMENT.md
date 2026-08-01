# Despliegue (Infra + Codigo)

Guia operativa para desplegar backend y frontend de `ai-agent` en GCP.

> **dev esta activo desde 2026-08-01; prod sigue hibernado.** Estado por ambiente, integraciones
> pendientes y orden de restauracion: `docs/HIBERNATION.md`.
>
> La SPA se sirve desde el mismo Cloud Run del backend. No hay load balancer ni dominio propio.

## Ambientes

| Ambiente | Proyecto GCP | Uso |
|----------|--------------|-----|
| `dev` | `ai-agent-calendar-dev` | Default de todos los comandos (`ENV ?= dev`) |
| `prod` | `ai-agent-calendar-2603011621` | Requiere `ENV=prod` explicito |

Todos los targets de deploy y de secrets aceptan `ENV=dev|prod`. Cada modulo Terraform tiene
`envs/{dev,prod}.tfvars` y el state vive en GCS (`<project_id>-tf-state`, prefijo por ambiente).

## Requisitos
- `gcloud`, `terraform`, `docker`, `npm`, `uv`
- Sesion activa en GCP:
  - `gcloud auth login`
  - `gcloud auth application-default login`
  - `gcloud config set project ai-agent-calendar-dev` (o el de prod)

## Archivos de infraestructura local

### Dockerfiles
- `Dockerfile.backend` — imagen de backend (Python slim + uv).
- `frontend/Dockerfile` — imagen de frontend (Node alpine).

### docker-compose.yml
- Servicios `backend` + `frontend` para desarrollo local.
- Uso: `make docker-up-build` (no es el flujo principal; para dev local preferir `make fe-dev` + `uv run uvicorn ...`).

### Modulos Terraform (`infra/terraform/`)
| Modulo | Que gestiona |
|--------|--------------|
| `project_bootstrap` | Proyecto, APIs, Firestore, secrets OAuth |
| `runtime_deploy` | Cloud Run, Artifact Registry, Cloud Tasks, Secret Manager, IAM |
| `frontend_spa_cdn` | Bucket GCS, HTTPS LB, Cloud CDN, certificados. **Fuera del flujo de deploy** desde 2026-08-01: la SPA se sirve desde Cloud Run. Se conserva por si vuelve a hacer falta un dominio propio |
| `github_wif` | Workload Identity Federation para GitHub Actions |

### Flujo Terraform local
- Al hacer deploy, Make copia via rsync a `.make-flow/deploy/terraform/{module}_local/` como working copies.
- No editar archivos en `.make-flow/` directamente; editar siempre en `infra/terraform/`.

## Variables y archivos usados por Make
- Salida backend deploy: `.make-flow/deploy/back.env`
- Salida frontend deploy: `.make-flow/deploy/front.env`
- API base para comandos make: `.secrets/make_api_base.env`
- Credenciales para comandos make: `.secrets/make_credentials.env`

## Despliegue de backend

```bash
make deploy-back            # dev
make deploy-back ENV=prod   # prod
```

Que hace:
- Provisiona/actualiza runtime infra con Terraform (`infra/terraform/runtime_deploy`)
- Construye y sube imagen Docker a Artifact Registry
- Actualiza Cloud Run
- Guarda la URL resultante en `.make-flow/deploy/back.env`

Si `DEPLOY_PROJECT_ID` no se pasa, se lee del `project_id` del `envs/<ENV>.tfvars`; el bucket de state
por defecto es `<project_id>-tf-state`.

## Despliegue de frontend

No hay un deploy de frontend separado. La SPA se compila en la primera etapa de
`Dockerfile.backend` (`node:22-alpine` → `npm ci` + `vite build`) y viaja dentro de la imagen; FastAPI
la sirve desde `src/entrypoints/web/static_spa.py`. Un cambio en `frontend/**` se publica con
`make deploy-back`.

Implicaciones:
- **Un solo origen**: la SPA y la API comparten dominio, asi que `VITE_API_BASE_URL` queda vacio en el
  build (rutas relativas) y no hay CORS entre ambos.
- **Sin costo fijo**: no hay load balancer, IP estatica, certificados ni bucket. HTTPS lo aporta el
  dominio `*.run.app`.
- **Sin dominio propio**: la app vive en la URL de Cloud Run. Para volver a un dominio propio esta el
  modulo `infra/terraform/frontend_spa_cdn`, que sigue en el repo pero fuera del flujo de deploy.
- Las herramientas internas (pagina de Evaluacion, prompt-preview) se controlan con el build arg
  `VITE_SHOW_INTERNAL_TOOLS`: `true` en dev, `false` en prod.

## Desplegar todo

```bash
make deploy-all ENV=prod
```

Alias de `deploy-back`: backend y SPA se publican juntos.

## CI/CD (GitHub Actions)

| Workflow | Trigger | Que hace |
|----------|---------|----------|
| `.github/workflows/ci.yml` | PRs y push a `develop` | ruff, mypy, bandit, pytest, checks de frontend y `terraform plan` |
| `.github/workflows/deploy-main.yml` | push a `develop` (→ dev) o `workflow_dispatch` con selector `dev`/`prod` | Deploy de backend + SPA con WIF (sin JSON keys). `frontend/**` dispara este job porque la SPA va en la imagen |
| `.github/workflows/deploy-dev.yml` | `workflow_dispatch` con un `ref` arbitrario | Despliega una rama/tag/SHA a dev; usa `paths-filter` contra `develop` para saltarse lo que no cambio |

Los secrets viven en GitHub Environments (`dev` y `prod`), no a nivel de repo. Detalle de setup y
lista de secrets por ambiente: `docs/MANUAL_SETUP_DEV_ENV.md`.

## Configuracion runtime (Secret Manager JSON)
El backend lee toda su configuracion desde el secret `AI_AGENT_APP_CONFIG_JSON` al arrancar.

Upsert de una llave:

```bash
make app-config-secret-upsert \
  ENV=prod \
  APP_CONFIG_PAIR='META_WEBHOOK_VERIFY_TOKEN:dev-meta-webhook-verify-token123'
```

Varias llaves de una:

```bash
make app-config-secret-upsert-many \
  ENV=prod \
  APP_CONFIG_PAIRS='META_APP_ID:123 META_APP_SECRET:abc'
```

Valores tipados (numero, bool, array) con JSON:

```bash
make app-config-secret-upsert \
  ENV=prod \
  APP_CONFIG_KEY=CONTEXT_MESSAGE_LIMIT \
  APP_CONFIG_VALUE_JSON=50
```

Sincronizar desde `.env`:

```bash
make app-config-secret-sync-env ENV=prod APP_CONFIG_ENV_FILE=.env
```

Con `APP_CONFIG_PRUNE_ENV=true` se eliminan del `.env` las llaves ya subidas.

Despues de cambiar el secret, redeploy del backend para que lo tome:

```bash
make deploy-back ENV=prod
```

## Comandos utiles de operacion local

```bash
make save-api-base API_BASE=https://<cloud-run-url>   # guarda la URL para los demas targets
make chat-memory-reset                                 # reset de memoria de chat
make list-professionals                                # lista tenants/profesionales
make resubscribe-waba                                  # re-suscribe la app al WABA
make calendar-cleanup                                  # limpia eventos de prueba en Calendar
```

## APIs de GCP gestionadas por Terraform
Se declaran en `infra/terraform/project_bootstrap/variables.tf` (`enable_apis`). Si se necesita una API
nueva, agregarla ahi para que Terraform siga siendo la fuente de verdad.

Default actual: `calendar-json`, `secretmanager`, `stitch`. Firestore se habilita aparte con
`enable_firestore`. Las APIs de runtime (Cloud Run, Artifact Registry, Cloud Tasks, Compute) se
habilitan en el setup del proyecto — ver `docs/MANUAL_SETUP_DEV_ENV.md`, paso 2.

## Verificacion rapida post-deploy
- Readiness (chequea Firestore): `https://<cloud-run-url>/readyz` — debe responder `{"status":"ok"}`
- SPA: `https://<cloud-run-url>/` y un deep link como `/login` (valida el fallback a `index.html`)
- Backend docs: `https://<cloud-run-url>/docs`

> **`/healthz` no sirve como verificacion externa en Cloud Run.** Google Front End intercepta ese path
> exacto y responde su propio 404 sin llegar al contenedor (se nota porque la respuesta no trae
> `x-request-id` ni `server: Google Frontend`). El endpoint existe y funciona dentro del contenedor;
> para chequear desde afuera usar `/readyz`.

## Regla de commits
Ver "Principios de Trabajo" en `CLAUDE.md` (fuente canonica).
