# GitHub WIF Bootstrap (Terraform)

Este stack crea el acceso seguro desde GitHub Actions a GCP sin llaves JSON:

1. Service Account deployer para CI/CD.
2. Service Account runtime para Cloud Run.
3. Workload Identity Pool + Provider para OIDC de GitHub.
4. IAM minimo para que el deployer pueda aplicar el stack de runtime.

## Requisitos

1. `terraform` y `gcloud` instalados.
2. Permisos admin iniciales en el proyecto para bootstrap.

## Uso

```bash
cd infra/terraform/github_wif
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars`:

1. `project_id`
2. `github_repository` (formato `owner/repo`)
3. `github_branch` (por defecto `main`)

Luego:

```bash
terraform init
terraform plan
terraform apply
```

## Outputs que debes llevar a GitHub

1. `workload_identity_provider_name` -> secret `GCP_WIF_PROVIDER`
2. `deployer_service_account_email` -> secret `GCP_WIF_SERVICE_ACCOUNT`
3. `runtime_service_account_email` -> variable/secret `RUNTIME_SERVICE_ACCOUNT_EMAIL`

Tambien define en GitHub:

1. `GCP_PROJECT_ID`
2. `GCP_REGION`
3. `GCP_ARTIFACT_REPOSITORY`

Estos los consume el workflow de deploy en `.github/workflows/deploy-main.yml`.
