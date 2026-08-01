# Hibernacion y Restauracion de Infraestructura

Historial de la pausa del proyecto y estado vigente de cada ambiente.

## Estado actual

| Ambiente | Proyecto GCP | Estado | URL |
|----------|--------------|--------|-----|
| dev | `ai-agent-calendar-dev` | **Activo** desde 2026-08-01 | `https://ai-agent-backend-rydex7ofva-uc.a.run.app` |
| prod | `ai-agent-calendar-2603011621` | Hibernado desde 2026-05-26 | — |

En dev corren Cloud Run (`min_instances=0`), Artifact Registry, Cloud Tasks y el secret
`AI_AGENT_APP_CONFIG_JSON`. La SPA se sirve desde el mismo servicio de Cloud Run: **no hay load
balancer, CDN, IP estatica, certificados ni bucket de frontend en ningun ambiente.**

## Que quedo pendiente en dev

El ambiente se levanto con alcance "app web": login y panel contra Firestore. Falta configurar las
integraciones externas, cuyas credenciales se perdieron con el borrado del secret (Secret Manager no
tiene recuperacion):

| Integracion | Llaves faltantes | Donde se recuperan |
|-------------|------------------|--------------------|
| WhatsApp / Meta | `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID`, `META_REDIRECT_URI`, `META_WEBHOOK_VERIFY_TOKEN` | Consola de Meta for Developers |
| Google Calendar | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` | GCP Console → APIs & Services → Credentials |
| Trazas | `LANGSMITH_API_KEY` | Consola de LangSmith |
| Email | `RESEND_API_KEY` | Consola de Resend |

Mientras falten las de Meta, el secret tiene `WHATSAPP_OUTBOUND_NOOP=true` para que la app no intente
enviar mensajes que fallarian.

**La URL de Cloud Run no cambio al recrear el servicio** (el hash resulto estable para el mismo
proyecto + servicio + region), asi que los redirect URIs registrados antes en Meta y Google siguen
siendo validos. Conviene confirmarlo en cada consola antes de dar la integracion por buena.

## Que se destruyo en la hibernacion (2026-05-26)

### Prod (`ai-agent-calendar-2603011621`)

| Modulo TF | Recursos eliminados |
|-----------|-------------------|
| `frontend_spa_cdn` | Global forwarding rules (HTTPS:443 + HTTP redirect:80), static IP `130.211.34.64`, HTTPS/HTTP proxies, URL maps, backend bucket + CDN, SSL certs (`alejaescobar.com`, `agendachat.app`), GCS bucket `ai-agent-calendar-2603011621-frontend-spa` |
| `runtime_deploy` | Cloud Run `ai-agent-backend` (min_instances=1, cpu always-on), Artifact Registry repo (5.3 GB Docker images), Cloud Tasks queue `scheduling-tasks`, Secret Manager secret `AI_AGENT_APP_CONFIG_JSON`, IAM bindings |

### Dev (`ai-agent-calendar-dev`)

| Modulo TF | Recursos eliminados |
|-----------|-------------------|
| `frontend_spa_cdn` | Global forwarding rule (HTTP:80), static IP `35.186.194.28`, HTTP proxy, URL map, backend bucket, GCS bucket `ai-agent-calendar-dev-frontend-spa` |
| `runtime_deploy` | Cloud Run `ai-agent-backend` (min_instances=0), Artifact Registry repo (35.7 GB Docker images), Cloud Tasks queue `scheduling-tasks`, Secret Manager secret `AI_AGENT_APP_CONFIG_JSON`, IAM bindings |

Costo eliminado: ~$78/mes (LBs ~$68 + Cloud Run prod min=1 ~$7-10 + Artifact Registry dev 35 GB ~$3.57).

Los proyectos GCP, los buckets `*-tf-state`, las bases de Firestore y el Workload Identity Federation
de GitHub Actions nunca se tocaron. Los datos de Firestore sobrevivieron intactos en ambos ambientes.

## Como restaurar un ambiente

### Prerequisitos

- `gcloud`, `terraform`, `docker`, `npm`, `uv` instalados
- `gcloud config configurations activate personal`
- ADC vigente en `.secrets/gcp-adc-gmail.json`

### Paso 1: crear la infra y cargar el secret

El primer `deploy-back` en un proyecto vacio **falla a proposito**: crea el secret
`AI_AGENT_APP_CONFIG_JSON` sin ninguna version, y Cloud Run no puede arrancar sin poder leerlo.

```bash
make deploy-back ENV=dev   # crea Artifact Registry, Cloud Run, Cloud Tasks y el secret vacio
```

Cargar la configuracion minima antes de reintentar. Solo `JWT_SECRET` es obligatorio; el resto tiene
defaults:

```bash
make app-config-secret-upsert-many ENV=dev APP_CONFIG_PAIRS='JWT_SECRET:<generar-uno-nuevo> GOOGLE_CLOUD_PROJECT:ai-agent-calendar-dev'
```

O cargar un JSON completo de una:

```bash
gcloud secrets versions add AI_AGENT_APP_CONFIG_JSON \
  --project=ai-agent-calendar-dev --data-file=<archivo.json>
```

### Paso 2: desplegar

```bash
make deploy-back ENV=dev
```

Esto compila la SPA dentro de la imagen, la sube a Artifact Registry y actualiza Cloud Run. La URL
resultante queda en `.make-flow/deploy/dev-back.env`.

### Paso 3: apuntar la config a la URL resultante

```bash
URL=$(grep '^DEPLOY_BACKEND_URL=' .make-flow/deploy/dev-back.env | cut -d= -f2-)
make app-config-secret-upsert ENV=dev APP_CONFIG_PAIR="FRONTEND_APP_BASE_URL:$URL"
make app-config-secret-upsert ENV=dev APP_CONFIG_PAIR="CLOUD_RUN_BASE_URL:$URL"
make app-config-secret-upsert ENV=dev APP_CONFIG_PAIR="CORS_ALLOWED_ORIGINS:$URL"
make deploy-back ENV=dev   # redeploy para que el contenedor lea la config nueva
```

`CLOUD_RUN_BASE_URL` es lo que usa Cloud Tasks para los callbacks de auto-cierre y recordatorios;
sin el, esas tareas no se encolan.

### Paso 4: verificar

```bash
curl https://<cloud-run-url>/readyz    # {"status":"ok"} con firestore ok
curl -o /dev/null -w '%{http_code}\n' https://<cloud-run-url>/login   # 200 (deep link de la SPA)
```

Ver la nota sobre `/healthz` en `docs/DEPLOYMENT.md`: ese path lo intercepta Google Front End y no
sirve para verificar desde afuera.

## Notas

- Las **imagenes Docker** se reconstruyen solas en cada `deploy-back`. Desde 2026-08-01 el repo de
  Artifact Registry tiene politicas de limpieza (5 imagenes recientes + borrado a los 30 dias), asi
  que ya no puede volver a crecer a decenas de GB.
- El **JWT_SECRET nuevo invalida las sesiones activas** pero no las contrasenas: los `password_hash`
  viven en Firestore y siguen siendo validos. Los `refresh_tokens` viejos quedan inservibles.
- El **Workload Identity Federation** sigue activo en ambos proyectos, con su pool y service account
  de deploy. El CI/CD funciona en cualquiera de los dos ambientes de forma independiente.
