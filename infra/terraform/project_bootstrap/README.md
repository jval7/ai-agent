# Project Bootstrap (GCP)

Este stack crea un proyecto nuevo en GCP, lo asocia a billing y habilita APIs base.

## Requisitos

1. Tener permisos para crear proyectos y vincular billing.
2. Tener `gcloud` y `terraform` instalados.
3. Login en gcloud con tu cuenta principal:

```bash
gcloud auth login
gcloud auth application-default login
```

## 1) Obtener billing account ID

```bash
gcloud billing accounts list
```

## 2) Configurar variables

```bash
cd infra/terraform/project_bootstrap
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars`:

1. `project_id`
2. `project_name`
3. `billing_account_id`
4. `org_id` o `folder_id` solo si aplica

Para cuenta personal, deja `org_id=null` y `folder_id=null`.

## 3) Crear proyecto

```bash
terraform init
terraform plan
terraform apply
```

## 4) Siguiente paso para OAuth Calendar

Despues de crear el proyecto, sigue con:

1. `infra/terraform/hybrid_oauth/README.md` para secretos/APIs OAuth del backend.
2. Crear manualmente el OAuth Client ID de Calendar en Google Cloud Console.

Motivo: hoy no hay recurso nativo estable del provider para ese OAuth client de Calendar.
