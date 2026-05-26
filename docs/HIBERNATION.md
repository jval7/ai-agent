# Hibernacion de Infraestructura

Registro de la pausa del proyecto y guia para restaurar.

## Fecha de hibernacion

**2026-05-26**

## Que se destruyo

Todos los recursos con costo fijo mensual se eliminaron via `terraform destroy` en ambos ambientes.

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

### Costo eliminado

~$78/mes (LBs ~$68 + Cloud Run prod min=1 ~$7-10 + Artifact Registry dev 35GB ~$3.57)

## Que se preservo

| Recurso | Env | Razon |
|---------|-----|-------|
| Proyectos GCP | Ambos | Recrear proyectos es costoso (APIs, IAM, Firestore location). Costo: $0 |
| GCS buckets de TF state (`*-tf-state`) | Ambos | Contienen el state de Terraform (vacio post-destroy). Necesarios para re-deploy limpio. Costo: centavos |
| Firestore databases | Ambos | Datos de usuarios. Free tier. Costo: $0 |
| `project_bootstrap` module | Ambos | Gestiona Firestore + OAuth secrets + APIs base. Sin costo fijo |
| `github_wif` module | Prod | Workload Identity Federation para GitHub Actions CI/CD. Sin costo fijo |

## Como restaurar

### Prerequisitos

- `gcloud`, `terraform`, `docker`, `npm`, `uv` instalados
- Sesion activa: `gcloud config configurations activate personal`
- ADC vigente (ver `CLAUDE.md` raiz para renovar si expiro)

### Paso 1: Deploy backend (por env)

```bash
# Prod
make deploy-back ENV=prod

# Dev
make deploy-back ENV=dev
```

Esto recrea: Artifact Registry, Cloud Run, Cloud Tasks, Secret Manager secret + IAM.

### Paso 2: Re-sync secrets

Los secrets (`AI_AGENT_APP_CONFIG_JSON`) se recrean vacios. Hay que re-poblarlos:

```bash
# Sincronizar desde .env local
make app-config-secret-sync-env \
  DEPLOY_PROJECT_ID=ai-agent-calendar-2603011621 \
  APP_CONFIG_ENV_FILE=.env

# Repetir para dev si aplica
make app-config-secret-sync-env \
  DEPLOY_PROJECT_ID=ai-agent-calendar-dev \
  APP_CONFIG_ENV_FILE=.env.dev
```

Despues redeploy backend para que tome los secrets:

```bash
make deploy-back ENV=prod
make deploy-back ENV=dev
```

### Paso 3: Deploy frontend (por env)

```bash
# Prod
make deploy-front ENV=prod

# Dev
make deploy-front ENV=dev
```

Esto recrea: GCS bucket, LB, CDN (prod), SSL certs (prod), forwarding rules.

### Paso 4: Actualizar DNS

La IP publica sera nueva (la anterior se libero). Despues del deploy, obtener la nueva IP:

```bash
# La IP sale en el output del deploy, o:
gcloud compute addresses list --project=ai-agent-calendar-2603011621 --global
```

Actualizar los registros DNS A en el registrar de:
- `agendachat.app` -> nueva IP
- `alejaescobar.com` -> nueva IP (si aun se usa)

### Paso 5: Esperar SSL

Los managed SSL certs tardan entre 15 minutos y 24 horas en provisionar despues de que el DNS apunte a la nueva IP. Verificar:

```bash
gcloud compute ssl-certificates describe ai-agent-frontend-cert \
  --project=ai-agent-calendar-2603011621 \
  --global --format="value(managed.status)"
```

Debe mostrar `ACTIVE`.

### Paso 6: Verificar

```bash
# Backend
curl https://<cloud-run-url>/healthz

# Frontend
curl -I https://agendachat.app
```

## Notas importantes

- Las **imagenes Docker** se perdieron (Artifact Registry destruido). `make deploy-back` las reconstruye automaticamente.
- Los **datos de Firestore** estan intactos (no se toco `project_bootstrap`).
- El **Workload Identity Federation** (GitHub Actions CI/CD) sigue activo — los deploys automaticos funcionaran una vez restaurada la infra.
- Si el `.env` local se perdio, los valores de los secrets hay que recuperarlos manualmente (Meta webhook token, OAuth credentials, etc).
