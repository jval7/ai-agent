# Frontend SPA CDN (Cloud Storage + HTTPS LB + Cloud CDN)

Este stack crea infraestructura para servir React/Vite como SPA:

1. Bucket de Cloud Storage para assets estaticos.
2. Backend bucket con Cloud CDN.
3. HTTPS Load Balancer global con IP fija.
4. Certificado SSL administrado por Google (opcional).
5. Redirect HTTP -> HTTPS (opcional).

## Requisitos

1. Proyecto GCP activo (ejemplo: `ai-agent-dev-12345`).
2. Dominio propio para frontend (solo si activas HTTPS).
3. WIF/credenciales con permisos de `compute`, `storage` y `serviceusage`.
4. Bucket de remote state listo (`TF_STATE_BUCKET`).

## Uso

```bash
cd infra/terraform/frontend_spa_cdn
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars`:

1. `project_id`
2. `enable_https` y `frontend_domains` (si quieres dominio+certificado)
3. `bucket_name` (opcional, debe ser globalmente unico)

Inicializa y despliega:

```bash
terraform init -reconfigure \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="prefix=ai-agent/frontend_spa_cdn"

terraform plan
terraform apply
```

## DNS y certificado

Solo si `enable_https=true`, despues del `apply`:

1. Toma `frontend_load_balancer_ip` de outputs.
2. Crea registro `A` del dominio frontend hacia esa IP.
3. Espera propagacion DNS y provisioning del certificado administrado.

## Modo rapido local (sin dominio)

Si quieres iterar rapido por IP:

1. `enable_https = false`
2. `enable_http_redirect = false`
3. `frontend_domains = []`

Terraform crea listener HTTP y puedes entrar por `frontend_http_url`.

## Subir build del frontend

En la raiz del repo:

```bash
cd frontend
npm ci
npm run build
cd ..
```

Sube artifacts:

```bash
gcloud storage rsync --recursive ./frontend/dist gs://<frontend_bucket_name>
```

Recomendacion de cache:

1. `index.html` con `Cache-Control: no-cache`.
2. assets con hash (`/assets/*`) con cache largo.
