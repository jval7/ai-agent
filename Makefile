SHELL := /bin/zsh

ifneq (,$(wildcard .env))
include .env
export
endif

MAKE_CREDENTIALS_FILE ?= .secrets/make_credentials.env
ifneq (,$(wildcard $(MAKE_CREDENTIALS_FILE)))
include $(MAKE_CREDENTIALS_FILE)
export
endif

MAKE_API_BASE_FILE ?= .secrets/make_api_base.env
ifneq (,$(wildcard $(MAKE_API_BASE_FILE)))
include $(MAKE_API_BASE_FILE)
export
endif

API_BASE ?= http://localhost:8000
TENANT_NAME ?= Acme
OWNER_EMAIL ?= owner@acme.com
OWNER_PASSWORD ?= supersecret
MASTER_EMAIL ?= $(OWNER_EMAIL)
MASTER_PASSWORD ?= $(OWNER_PASSWORD)
USER_EMAIL ?=
USER_PASSWORD ?=
OWNER_EMAIL_ORIGIN := $(origin OWNER_EMAIL)
OWNER_PASSWORD_ORIGIN := $(origin OWNER_PASSWORD)
FLOW_DIR ?= .make-flow
FRONTEND_DIR ?= frontend
SIM_WA_USER_ID ?= 573001234567
SIM_WA_USER_NAME ?= Cliente Demo
MESSAGE ?= Hola desde WhatsApp
SIM_PROVIDER_MESSAGE_ID ?=
DEPLOY_PROJECT_ID ?= ai-agent-calendar-2603011621
DEPLOY_REGION ?= us-central1
DEPLOY_ARTIFACT_REPOSITORY ?= ai-agent-backend
DEPLOY_CLOUD_RUN_SERVICE_NAME ?= ai-agent-backend
DEPLOY_RUNTIME_SERVICE_ACCOUNT_EMAIL ?=
DEPLOY_BACKEND_IMAGE_TAG ?=
DEPLOY_MIN_INSTANCES ?= 0
DEPLOY_BACKEND_URL ?=
DEPLOY_FRONTEND_BUCKET_NAME ?=
DEPLOY_FRONTEND_BUCKET_LOCATION ?= US
DEPLOY_FRONTEND_RESOURCE_PREFIX ?= ai-agent-frontend
DEPLOY_FRONTEND_ENABLE_HTTPS ?= false
DEPLOY_FRONTEND_ENABLE_HTTP_REDIRECT ?= false
DEPLOY_FRONTEND_DOMAINS ?=
DEPLOY_ENABLE_CDN ?= true
DEPLOY_FORCE_DESTROY_BUCKET ?= false
DEPLOY_APP_CONFIG_SECRET_ID ?= AI_AGENT_APP_CONFIG_JSON
DEPLOY_BASE_DIR ?= $(FLOW_DIR)/deploy
DEPLOY_STATE_DIR ?= $(DEPLOY_BASE_DIR)/state
DEPLOY_FRONT_TF_DIR ?= $(DEPLOY_BASE_DIR)/terraform/frontend_spa_cdn_local
DEPLOY_BACK_TF_DIR ?= $(DEPLOY_BASE_DIR)/terraform/runtime_deploy_local
DEPLOY_FRONT_STATE_FILE ?= $(DEPLOY_STATE_DIR)/frontend_spa_cdn.tfstate
DEPLOY_BACK_STATE_FILE ?= $(DEPLOY_STATE_DIR)/runtime_deploy.tfstate
DEPLOY_FRONT_ENV_FILE ?= $(DEPLOY_BASE_DIR)/front.env
DEPLOY_BACK_ENV_FILE ?= $(DEPLOY_BASE_DIR)/back.env
APP_CONFIG_KEY ?=
APP_CONFIG_VALUE ?=
APP_CONFIG_VALUE_JSON ?=
APP_CONFIG_PAIR ?=
APP_CONFIG_ENV_FILE ?= .env
APP_CONFIG_PRUNE_ENV ?= false
APP_CONFIG_SYNC_KEYS ?= JWT_SECRET JWT_ACCESS_TTL_SECONDS JWT_REFRESH_TTL_SECONDS DEFAULT_SYSTEM_PROMPT CONTEXT_MESSAGE_LIMIT FIRESTORE_DATABASE_ID CORS_ALLOWED_ORIGINS FRONTEND_APP_BASE_URL ENABLE_DEV_ENDPOINTS META_APP_ID META_APP_SECRET META_REDIRECT_URI META_WEBHOOK_VERIFY_TOKEN META_PHONE_REGISTRATION_PIN META_API_VERSION GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET GOOGLE_OAUTH_REDIRECT_URI GOOGLE_CLOUD_PROJECT GEMINI_LOCATION GEMINI_MODEL GEMINI_MAX_OUTPUT_TOKENS LANGSMITH_TRACING_ENABLED LANGSMITH_PROJECT LANGSMITH_API_KEY LANGSMITH_ENDPOINT LANGSMITH_WORKSPACE_ID LANGSMITH_ENVIRONMENT LANGSMITH_TAGS LOG_LEVEL LOG_INCLUDE_REQUEST_SUMMARY LANGCHAIN_API_KEY LANGCHAIN_ENDPOINT

.PHONY: \
	oauth-flow \
	user-bootstrap-master \
	user-create \
	user-delete \
	save-api-base \
	save-credentials \
	memory-reset \
	chat-memory-reset \
	static-checks \
	fe-install \
	fe-dev \
	fe-lint \
	fe-format \
	fe-format-check \
	fe-typecheck \
	fe-test \
	fe-security \
	fe-checks \
	checks \
	docker-up \
	docker-up-build \
	docker-down \
	docker-logs \
	deploy-front-infra \
	deploy-front-upload \
	deploy-front \
	deploy-back \
	deploy-all \
	app-config-secret-upsert \
	app-config-secret-sync-env \
	simulate-whatsapp-message

oauth-flow:
	@command -v jq >/dev/null 2>&1 || { echo "jq is required. Install with: brew install jq"; exit 1; }
	@mkdir -p "$(FLOW_DIR)"
	@login_response=$$(curl -sS -X POST "$(API_BASE)/v1/auth/login" \
		-H "Content-Type: application/json" \
		-d '{"email":"$(OWNER_EMAIL)","password":"$(OWNER_PASSWORD)"}'); \
	access_token=$$(echo "$$login_response" | jq -r '.access_token'); \
	if [[ "$$access_token" == "null" || -z "$$access_token" ]]; then \
		echo "Login failed:"; \
		echo "$$login_response" | jq . 2>/dev/null || echo "$$login_response"; \
		echo ""; \
		echo "Si es la primera vez en este ambiente, bootstrap del master:"; \
		echo "make user-bootstrap-master TENANT_NAME='$(TENANT_NAME)' MASTER_EMAIL='$(MASTER_EMAIL)' MASTER_PASSWORD='$(MASTER_PASSWORD)'"; \
		exit 1; \
	fi; \
	echo "$$access_token" > "$(FLOW_DIR)/access_token"; \
	session_response=$$(curl -sS -X POST "$(API_BASE)/v1/whatsapp/embedded-signup/session" \
		-H "Authorization: Bearer $$access_token"); \
	state=$$(echo "$$session_response" | jq -r '.state'); \
	connect_url=$$(echo "$$session_response" | jq -r '.connect_url'); \
	if [[ "$$state" == "null" || -z "$$state" || "$$connect_url" == "null" || -z "$$connect_url" ]]; then \
		echo "Session creation failed:"; \
		echo "$$session_response" | jq . 2>/dev/null || echo "$$session_response"; \
		exit 1; \
	fi; \
	echo "$$state" > "$(FLOW_DIR)/state"; \
	echo "$$connect_url" > "$(FLOW_DIR)/connect_url"; \
	echo "STATE=$$state"; \
	echo "CONNECT_URL=$$connect_url"; \
	if command -v open >/dev/null 2>&1; then \
		open "$$connect_url"; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open "$$connect_url"; \
	else \
		echo "No browser opener found. Open manually:"; \
		echo "$$connect_url"; \
	fi

save-api-base:
	@if [[ -z "$(API_BASE)" ]]; then \
		echo "API_BASE is required. Example: make save-api-base API_BASE=https://your-backend.run.app"; \
		exit 1; \
	fi
	@mkdir -p "$(dir $(MAKE_API_BASE_FILE))"
	@printf "API_BASE=%s\n" "$(API_BASE)" > "$(MAKE_API_BASE_FILE)"
	@chmod 600 "$(MAKE_API_BASE_FILE)"
	@echo "Saved API_BASE to $(MAKE_API_BASE_FILE)"

save-credentials:
	@mkdir -p "$(dir $(MAKE_CREDENTIALS_FILE))"
	@printf "OWNER_EMAIL=%s\nOWNER_PASSWORD=%s\n" "$(OWNER_EMAIL)" "$(OWNER_PASSWORD)" > "$(MAKE_CREDENTIALS_FILE)"
	@chmod 600 "$(MAKE_CREDENTIALS_FILE)"
	@echo "Saved OWNER_EMAIL/OWNER_PASSWORD to $(MAKE_CREDENTIALS_FILE)"

user-bootstrap-master:
	@uv run python -m src.entrypoints.local.user_admin_cli bootstrap-master \
		--tenant-name "$(TENANT_NAME)" \
		--master-email "$(MASTER_EMAIL)" \
		--master-password "$(MASTER_PASSWORD)"

user-create:
	@if [[ -z "$(USER_EMAIL)" ]]; then \
		echo "USER_EMAIL is required. Example: make user-create USER_EMAIL=user@acme.com USER_PASSWORD=supersecret"; \
		exit 1; \
	fi
	@if [[ -z "$(USER_PASSWORD)" ]]; then \
		echo "USER_PASSWORD is required. Example: make user-create USER_EMAIL=user@acme.com USER_PASSWORD=supersecret"; \
		exit 1; \
	fi
	@uv run python -m src.entrypoints.local.user_admin_cli create-user \
		--master-email "$(MASTER_EMAIL)" \
		--master-password "$(MASTER_PASSWORD)" \
		--email "$(USER_EMAIL)" \
		--password "$(USER_PASSWORD)"

user-delete:
	@if [[ -z "$(USER_EMAIL)" ]]; then \
		echo "USER_EMAIL is required. Example: make user-delete USER_EMAIL=user@acme.com"; \
		exit 1; \
	fi
	@uv run python -m src.entrypoints.local.user_admin_cli delete-user \
		--master-email "$(MASTER_EMAIL)" \
		--master-password "$(MASTER_PASSWORD)" \
		--email "$(USER_EMAIL)"

memory-reset:
	@if [[ -f "$(FLOW_DIR)/access_token" ]]; then \
		access_token=$$(cat "$(FLOW_DIR)/access_token"); \
		live_reset_response=$$(curl -sS -X POST "$(API_BASE)/v1/dev/memory/reset" \
			-H "Authorization: Bearer $$access_token" || true); \
		echo "Live reset response: $$live_reset_response"; \
	else \
		echo "No access token in $(FLOW_DIR)/access_token; skipping live reset endpoint."; \
	fi
	@echo "Firestore reset endpoint finished. No local JSON snapshot cleanup is required."

chat-memory-reset:
	@command -v jq >/dev/null 2>&1 || { echo "jq is required. Install with: brew install jq"; exit 1; }
	@mkdir -p "$(FLOW_DIR)"
	@live_reset_ok=0; \
	resolved_api_base="$(API_BASE)"; \
	if [[ "$$resolved_api_base" == "http://localhost:8000" && -f "$(DEPLOY_BACK_ENV_FILE)" ]]; then \
		deployed_backend_url=$$(grep '^DEPLOY_BACKEND_URL=' "$(DEPLOY_BACK_ENV_FILE)" | head -n 1 | cut -d '=' -f 2-); \
		if [[ -n "$$deployed_backend_url" ]]; then \
			resolved_api_base="$$deployed_backend_url"; \
			mkdir -p "$(dir $(MAKE_API_BASE_FILE))"; \
			printf "API_BASE=%s\n" "$$resolved_api_base" > "$(MAKE_API_BASE_FILE)"; \
			chmod 600 "$(MAKE_API_BASE_FILE)"; \
			echo "Saved API_BASE to $(MAKE_API_BASE_FILE) from $(DEPLOY_BACK_ENV_FILE)"; \
		fi; \
	fi; \
	echo "Using API_BASE=$$resolved_api_base"; \
	if [[ "$(OWNER_EMAIL_ORIGIN)" == "command line" || "$(OWNER_PASSWORD_ORIGIN)" == "command line" ]]; then \
		mkdir -p "$(dir $(MAKE_CREDENTIALS_FILE))"; \
		printf "OWNER_EMAIL=%s\nOWNER_PASSWORD=%s\n" "$(OWNER_EMAIL)" "$(OWNER_PASSWORD)" > "$(MAKE_CREDENTIALS_FILE)"; \
		chmod 600 "$(MAKE_CREDENTIALS_FILE)"; \
		echo "Saved credentials to $(MAKE_CREDENTIALS_FILE)"; \
	fi; \
	resolved_access_token=""; \
	if [[ -f "$(FLOW_DIR)/access_token" ]]; then \
		resolved_access_token=$$(cat "$(FLOW_DIR)/access_token"); \
	fi; \
	if [[ -n "$$resolved_access_token" ]]; then \
		live_chat_reset_response=$$(curl -sS -X POST "$$resolved_api_base/v1/dev/memory/chat/reset" \
			-H "Authorization: Bearer $$resolved_access_token" || true); \
		live_chat_reset_status=$$(echo "$$live_chat_reset_response" | jq -r '.status // empty' 2>/dev/null); \
		if [[ "$$live_chat_reset_status" == "chat_reset" ]]; then \
			live_reset_ok=1; \
			echo "Live chat reset response: $$live_chat_reset_response"; \
		else \
			echo "Stored access token did not reset chat memory; attempting login fallback."; \
		fi; \
	fi; \
	if [[ $$live_reset_ok -eq 0 ]]; then \
		login_response=$$(curl -sS -X POST "$$resolved_api_base/v1/auth/login" \
			-H "Content-Type: application/json" \
			-d '{"email":"$(OWNER_EMAIL)","password":"$(OWNER_PASSWORD)"}' || true); \
		login_access_token=$$(echo "$$login_response" | jq -r '.access_token // empty' 2>/dev/null); \
		if [[ -n "$$login_access_token" ]]; then \
			echo "$$login_access_token" > "$(FLOW_DIR)/access_token"; \
			live_chat_reset_response=$$(curl -sS -X POST "$$resolved_api_base/v1/dev/memory/chat/reset" \
				-H "Authorization: Bearer $$login_access_token" || true); \
			live_chat_reset_status=$$(echo "$$live_chat_reset_response" | jq -r '.status // empty' 2>/dev/null); \
			if [[ "$$live_chat_reset_status" == "chat_reset" ]]; then \
				live_reset_ok=1; \
				echo "Live chat reset response: $$live_chat_reset_response"; \
				mkdir -p "$(dir $(MAKE_CREDENTIALS_FILE))"; \
				printf "OWNER_EMAIL=%s\nOWNER_PASSWORD=%s\n" "$(OWNER_EMAIL)" "$(OWNER_PASSWORD)" > "$(MAKE_CREDENTIALS_FILE)"; \
				chmod 600 "$(MAKE_CREDENTIALS_FILE)"; \
				echo "Saved credentials to $(MAKE_CREDENTIALS_FILE)"; \
			else \
				echo "Live chat reset failed after login: $$live_chat_reset_response"; \
			fi; \
		else \
			echo "Login fallback failed; skipping live reset. Response: $$login_response"; \
		fi; \
	fi; \
	if [[ $$live_reset_ok -eq 0 ]]; then \
		echo "Live reset was not applied."; \
	fi
	@echo "Firestore chat reset endpoint finished. No local JSON snapshot cleanup is required."

static-checks:
	@uv run ruff check .
	@uv run ruff format --check .
	@uv run mypy src tests
	@uv run bandit -c pyproject.toml -r src

fe-install:
	@npm --prefix "$(FRONTEND_DIR)" install

fe-dev:
	@npm --prefix "$(FRONTEND_DIR)" run dev

fe-lint:
	@npm --prefix "$(FRONTEND_DIR)" run lint

fe-format:
	@npm --prefix "$(FRONTEND_DIR)" run format

fe-format-check:
	@npm --prefix "$(FRONTEND_DIR)" run format:check

fe-typecheck:
	@npm --prefix "$(FRONTEND_DIR)" run typecheck

fe-test:
	@npm --prefix "$(FRONTEND_DIR)" run test

fe-security:
	@npm --prefix "$(FRONTEND_DIR)" run security

fe-checks: fe-lint fe-format-check fe-typecheck fe-test fe-security

checks: static-checks fe-checks

docker-up:
	@docker compose up

docker-up-build:
	@docker compose up --build

docker-down:
	@docker compose down

docker-logs:
	@docker compose logs -f --tail=200

deploy-front-infra:
	@command -v terraform >/dev/null 2>&1 || { echo "terraform is required."; exit 1; }
	@mkdir -p "$(DEPLOY_FRONT_TF_DIR)"
	@mkdir -p "$(DEPLOY_STATE_DIR)"
	@rsync -a \
		--exclude='.terraform' \
		--exclude='terraform.tfstate' \
		--exclude='terraform.tfstate.backup' \
		--exclude='versions.tf' \
		infra/terraform/frontend_spa_cdn/ \
		"$(DEPLOY_FRONT_TF_DIR)/"
	@printf '%s\n' \
		'terraform {' \
		'  required_version = ">= 1.5.0"' \
		'' \
		'  backend "local" {' \
		'    path = "$(abspath $(DEPLOY_FRONT_STATE_FILE))"' \
		'  }' \
		'' \
		'  required_providers {' \
		'    google = {' \
		'      source  = "hashicorp/google"' \
		'      version = "~> 5.0"' \
		'    }' \
		'  }' \
		'}' \
		'' \
		'provider "google" {}' \
		> "$(DEPLOY_FRONT_TF_DIR)/versions.tf"
	@if [[ "$(DEPLOY_FRONTEND_ENABLE_HTTPS)" == "true" && -z "$(DEPLOY_FRONTEND_DOMAINS)" ]]; then \
		echo "DEPLOY_FRONTEND_DOMAINS is required when DEPLOY_FRONTEND_ENABLE_HTTPS=true"; \
		exit 1; \
	fi
	@domains_hcl=$$(echo "$(DEPLOY_FRONTEND_DOMAINS)" | awk -F',' '{ \
		printf "["; \
		sep=""; \
		for (i=1; i<=NF; i++) { \
			gsub(/^[[:space:]]+|[[:space:]]+$$/, "", $$i); \
			if (length($$i) > 0) { \
				printf "%s\"%s\"", sep, $$i; \
				sep=", "; \
			} \
		} \
		printf "]"; \
	}'); \
	printf '%s\n' \
		'project_id = "$(DEPLOY_PROJECT_ID)"' \
		'' \
		'enable_https         = $(DEPLOY_FRONTEND_ENABLE_HTTPS)' \
		'enable_http_redirect = $(DEPLOY_FRONTEND_ENABLE_HTTP_REDIRECT)' \
		"frontend_domains     = $${domains_hcl}" \
		'' \
		'bucket_name          = $(if $(DEPLOY_FRONTEND_BUCKET_NAME),"$(DEPLOY_FRONTEND_BUCKET_NAME)",null)' \
		'bucket_location      = "$(DEPLOY_FRONTEND_BUCKET_LOCATION)"' \
		'resource_name_prefix = "$(DEPLOY_FRONTEND_RESOURCE_PREFIX)"' \
		'enable_cdn           = $(DEPLOY_ENABLE_CDN)' \
		'force_destroy_bucket = $(DEPLOY_FORCE_DESTROY_BUCKET)' \
		'index_document       = "index.html"' \
		'error_document       = "index.html"' \
		> "$(DEPLOY_FRONT_TF_DIR)/terraform.tfvars"
	@terraform -chdir="$(DEPLOY_FRONT_TF_DIR)" init -migrate-state -force-copy
	@terraform -chdir="$(DEPLOY_FRONT_TF_DIR)" apply -auto-approve -var-file=terraform.tfvars
	@frontend_url=$$(terraform -chdir="$(DEPLOY_FRONT_TF_DIR)" output -raw frontend_http_url 2>/dev/null || true); \
	if [[ -z "$$frontend_url" || "$$frontend_url" == "null" ]]; then \
		frontend_url=$$(terraform -chdir="$(DEPLOY_FRONT_TF_DIR)" output -raw frontend_https_url); \
	fi; \
	frontend_bucket=$$(terraform -chdir="$(DEPLOY_FRONT_TF_DIR)" output -raw frontend_bucket_name); \
	mkdir -p "$(DEPLOY_BASE_DIR)"; \
	printf "DEPLOY_FRONTEND_URL=%s\nDEPLOY_FRONTEND_BUCKET=%s\n" "$$frontend_url" "$$frontend_bucket" > "$(DEPLOY_FRONT_ENV_FILE)"; \
	echo "Frontend infra ready: $$frontend_url (bucket=$$frontend_bucket)"

deploy-front-upload:
	@command -v gcloud >/dev/null 2>&1 || { echo "gcloud is required."; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "npm is required."; exit 1; }
	@backend_url="$(DEPLOY_BACKEND_URL)"; \
	if [[ -z "$$backend_url" && -f "$(DEPLOY_BACK_ENV_FILE)" ]]; then \
		backend_url=$$(grep '^DEPLOY_BACKEND_URL=' "$(DEPLOY_BACK_ENV_FILE)" | head -n 1 | cut -d '=' -f 2-); \
	fi; \
	if [[ -z "$$backend_url" ]]; then \
		echo "Set DEPLOY_BACKEND_URL or run make deploy-back first."; \
		exit 1; \
	fi; \
	frontend_bucket="$(DEPLOY_FRONTEND_BUCKET_NAME)"; \
	if [[ -z "$$frontend_bucket" && -f "$(DEPLOY_FRONT_ENV_FILE)" ]]; then \
		frontend_bucket=$$(grep '^DEPLOY_FRONTEND_BUCKET=' "$(DEPLOY_FRONT_ENV_FILE)" | head -n 1 | cut -d '=' -f 2-); \
	fi; \
	if [[ -z "$$frontend_bucket" ]]; then \
		frontend_bucket=$$(terraform -chdir="$(DEPLOY_FRONT_TF_DIR)" output -raw frontend_bucket_name 2>/dev/null || true); \
	fi; \
	if [[ -z "$$frontend_bucket" ]]; then \
		echo "Frontend bucket not found. Run make deploy-front-infra first."; \
		exit 1; \
	fi; \
	VITE_API_BASE_URL="$$backend_url" npm --prefix "$(FRONTEND_DIR)" run build; \
	gcloud storage rsync --recursive --delete-unmatched-destination-objects \
		"$(FRONTEND_DIR)/dist" \
		"gs://$$frontend_bucket"; \
	gcloud storage objects update "gs://$$frontend_bucket/index.html" \
		--cache-control="no-cache,max-age=0,must-revalidate"; \
	asset_objects=$$(gcloud storage ls "gs://$$frontend_bucket/assets/**" || true); \
	if [[ -n "$$asset_objects" ]]; then \
		while IFS= read -r object_uri; do \
			[[ "$$object_uri" == */ ]] && continue; \
			gcloud storage objects update "$$object_uri" \
				--cache-control="public,max-age=31536000,immutable"; \
		done <<< "$$asset_objects"; \
	fi; \
	echo "Frontend assets uploaded to gs://$$frontend_bucket using backend $$backend_url"

deploy-front: deploy-front-infra deploy-front-upload

deploy-back:
	@command -v terraform >/dev/null 2>&1 || { echo "terraform is required."; exit 1; }
	@command -v gcloud >/dev/null 2>&1 || { echo "gcloud is required."; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "docker is required."; exit 1; }
	@mkdir -p "$(DEPLOY_BACK_TF_DIR)"
	@mkdir -p "$(DEPLOY_STATE_DIR)"
	@rsync -a \
		--exclude='.terraform' \
		--exclude='terraform.tfstate' \
		--exclude='terraform.tfstate.backup' \
		--exclude='versions.tf' \
		infra/terraform/runtime_deploy/ \
		"$(DEPLOY_BACK_TF_DIR)/"
	@printf '%s\n' \
		'terraform {' \
		'  required_version = ">= 1.5.0"' \
		'' \
		'  backend "local" {' \
		'    path = "$(abspath $(DEPLOY_BACK_STATE_FILE))"' \
		'  }' \
		'' \
		'  required_providers {' \
		'    google = {' \
		'      source  = "hashicorp/google"' \
		'      version = "~> 5.0"' \
		'    }' \
		'  }' \
		'}' \
		'' \
		'provider "google" {}' \
		> "$(DEPLOY_BACK_TF_DIR)/versions.tf"
	@set -euo pipefail; \
	runtime_sa_email="$(DEPLOY_RUNTIME_SERVICE_ACCOUNT_EMAIL)"; \
	if [[ -z "$$runtime_sa_email" ]]; then \
		project_number=$$(gcloud projects describe "$(DEPLOY_PROJECT_ID)" --format='value(projectNumber)'); \
		runtime_sa_email="$$project_number-compute@developer.gserviceaccount.com"; \
	fi; \
	image_tag="$(DEPLOY_BACKEND_IMAGE_TAG)"; \
	if [[ -z "$$image_tag" ]]; then \
		image_tag=$$(date +%Y%m%d-%H%M%S)-amd64; \
	fi; \
	image_uri="$(DEPLOY_REGION)-docker.pkg.dev/$(DEPLOY_PROJECT_ID)/$(DEPLOY_ARTIFACT_REPOSITORY)/backend:$$image_tag"; \
	printf '%s\n' \
		'project_id                    = "$(DEPLOY_PROJECT_ID)"' \
		'region                        = "$(DEPLOY_REGION)"' \
		'artifact_registry_location    = "$(DEPLOY_REGION)"' \
		'artifact_repository_id        = "$(DEPLOY_ARTIFACT_REPOSITORY)"' \
		'cloud_run_service_name        = "$(DEPLOY_CLOUD_RUN_SERVICE_NAME)"' \
		"runtime_service_account_email = \"$$runtime_sa_email\"" \
		"container_image               = \"$$image_uri\"" \
		'' \
		'allow_unauthenticated = true' \
		'min_instances         = $(DEPLOY_MIN_INSTANCES)' \
		'max_instances         = 10' \
		'container_concurrency = 40' \
		'timeout_seconds       = 300' \
		'cpu                   = "1"' \
		'memory                = "512Mi"' \
		'container_port        = 8000' \
		'' \
		'manage_app_config_secret         = true' \
		'app_config_secret_bootstrap_json = "{}"' \
		> "$(DEPLOY_BACK_TF_DIR)/terraform.tfvars"; \
	terraform -chdir="$(DEPLOY_BACK_TF_DIR)" init -migrate-state -force-copy; \
	if ! terraform -chdir="$(DEPLOY_BACK_TF_DIR)" state show 'google_artifact_registry_repository.backend' >/dev/null 2>&1; then \
		terraform -chdir="$(DEPLOY_BACK_TF_DIR)" import -var-file=terraform.tfvars \
			'google_artifact_registry_repository.backend' \
			"projects/$(DEPLOY_PROJECT_ID)/locations/$(DEPLOY_REGION)/repositories/$(DEPLOY_ARTIFACT_REPOSITORY)" >/dev/null 2>&1 || true; \
	fi; \
	if ! terraform -chdir="$(DEPLOY_BACK_TF_DIR)" state show 'google_secret_manager_secret.app_config_json[0]' >/dev/null 2>&1; then \
		terraform -chdir="$(DEPLOY_BACK_TF_DIR)" import -var-file=terraform.tfvars \
			'google_secret_manager_secret.app_config_json[0]' \
			"projects/$(DEPLOY_PROJECT_ID)/secrets/$(DEPLOY_APP_CONFIG_SECRET_ID)" >/dev/null 2>&1 || true; \
	fi; \
	if ! terraform -chdir="$(DEPLOY_BACK_TF_DIR)" state show 'google_cloud_run_v2_service.backend' >/dev/null 2>&1; then \
		terraform -chdir="$(DEPLOY_BACK_TF_DIR)" import -var-file=terraform.tfvars \
			'google_cloud_run_v2_service.backend' \
			"projects/$(DEPLOY_PROJECT_ID)/locations/$(DEPLOY_REGION)/services/$(DEPLOY_CLOUD_RUN_SERVICE_NAME)" >/dev/null 2>&1 || true; \
	fi; \
	if ! terraform -chdir="$(DEPLOY_BACK_TF_DIR)" state show 'google_secret_manager_secret_iam_member.runtime_secret_accessor["$(DEPLOY_APP_CONFIG_SECRET_ID)"]' >/dev/null 2>&1; then \
		terraform -chdir="$(DEPLOY_BACK_TF_DIR)" import -var-file=terraform.tfvars \
			'google_secret_manager_secret_iam_member.runtime_secret_accessor["$(DEPLOY_APP_CONFIG_SECRET_ID)"]' \
			"projects/$(DEPLOY_PROJECT_ID)/secrets/$(DEPLOY_APP_CONFIG_SECRET_ID)/roles/secretmanager.secretAccessor/serviceAccount:$$runtime_sa_email" >/dev/null 2>&1 || true; \
	fi; \
	terraform -chdir="$(DEPLOY_BACK_TF_DIR)" apply -auto-approve -var-file=terraform.tfvars \
		-target=google_project_service.serviceusage \
		-target=google_project_service.apis \
		-target=google_artifact_registry_repository.backend; \
	gcloud auth configure-docker "$(DEPLOY_REGION)-docker.pkg.dev" --quiet; \
	docker buildx build --platform linux/amd64 -f Dockerfile.backend -t "$$image_uri" --push .; \
	terraform -chdir="$(DEPLOY_BACK_TF_DIR)" apply -auto-approve -var-file=terraform.tfvars; \
	backend_url=$$(terraform -chdir="$(DEPLOY_BACK_TF_DIR)" output -raw cloud_run_service_url); \
	mkdir -p "$(DEPLOY_BASE_DIR)"; \
	printf "DEPLOY_BACKEND_URL=%s\nDEPLOY_BACKEND_IMAGE_URI=%s\nDEPLOY_RUNTIME_SERVICE_ACCOUNT_EMAIL=%s\n" "$$backend_url" "$$image_uri" "$$runtime_sa_email" > "$(DEPLOY_BACK_ENV_FILE)"; \
	echo "Backend deployed: $$backend_url"

deploy-all:
	@$(MAKE) deploy-front-infra
	@$(MAKE) deploy-back
	@$(MAKE) deploy-front-upload

app-config-secret-upsert:
	@command -v gcloud >/dev/null 2>&1 || { echo "gcloud is required."; exit 1; }
	@command -v jq >/dev/null 2>&1 || { echo "jq is required."; exit 1; }
	@current_json=$$(gcloud secrets versions access latest \
		--project "$(DEPLOY_PROJECT_ID)" \
		--secret "$(DEPLOY_APP_CONFIG_SECRET_ID)" 2>/dev/null || echo "{}"); \
	if ! printf '%s' "$$current_json" | jq -e 'type=="object"' >/dev/null; then \
		echo "Current secret payload is not a JSON object."; \
		exit 1; \
	fi; \
	resolved_key="$(APP_CONFIG_KEY)"; \
	resolved_value="$(APP_CONFIG_VALUE)"; \
	resolved_value_json="$(APP_CONFIG_VALUE_JSON)"; \
	resolved_pair="$(APP_CONFIG_PAIR)"; \
	if [[ -n "$${resolved_pair}" ]]; then \
		if [[ "$${resolved_key}" != "" || "$${resolved_value}" != "" || "$${resolved_value_json}" != "" ]]; then \
			echo "Use APP_CONFIG_PAIR alone, or APP_CONFIG_KEY + APP_CONFIG_VALUE/APP_CONFIG_VALUE_JSON."; \
			exit 1; \
		fi; \
		if [[ "$${resolved_pair}" != *:* ]]; then \
			echo "APP_CONFIG_PAIR must have format LLAVE:VALOR"; \
			exit 1; \
		fi; \
		resolved_key="$${resolved_pair%%:*}"; \
		resolved_value="$${resolved_pair#*:}"; \
	fi; \
	if [[ -z "$${resolved_key}" ]]; then \
		echo "APP_CONFIG_KEY is required. Example: make app-config-secret-upsert APP_CONFIG_KEY=META_REDIRECT_URI APP_CONFIG_VALUE=https://..."; \
		echo "Or use: make app-config-secret-upsert APP_CONFIG_PAIR='META_REDIRECT_URI:https://...';"; \
		exit 1; \
	fi; \
	if [[ -z "$${resolved_value}" && -z "$${resolved_value_json}" ]]; then \
		echo "Set APP_CONFIG_VALUE (string) or APP_CONFIG_VALUE_JSON (typed JSON)."; \
		exit 1; \
	fi; \
	if [[ -n "$${resolved_value}" && -n "$${resolved_value_json}" ]]; then \
		echo "Use only one: APP_CONFIG_VALUE or APP_CONFIG_VALUE_JSON."; \
		exit 1; \
	fi; \
	if [[ -n "$${resolved_value_json}" ]]; then \
		updated_json=$$(printf '%s' "$$current_json" \
			| jq --arg key "$${resolved_key}" --argjson value "$${resolved_value_json}" '.[$$key] = $$value'); \
	else \
		updated_json=$$(printf '%s' "$$current_json" \
			| jq --arg key "$${resolved_key}" --arg value "$${resolved_value}" '.[$$key] = $$value'); \
	fi; \
	printf '%s' "$$updated_json" | gcloud secrets versions add "$(DEPLOY_APP_CONFIG_SECRET_ID)" \
		--project "$(DEPLOY_PROJECT_ID)" \
		--data-file=- >/dev/null; \
	echo "Upserted key '$${resolved_key}' in secret $(DEPLOY_APP_CONFIG_SECRET_ID)."

app-config-secret-sync-env:
	@command -v gcloud >/dev/null 2>&1 || { echo "gcloud is required."; exit 1; }
	@command -v jq >/dev/null 2>&1 || { echo "jq is required."; exit 1; }
	@if [[ ! -f "$(APP_CONFIG_ENV_FILE)" ]]; then \
		echo "Env file not found: $(APP_CONFIG_ENV_FILE)"; \
		exit 1; \
	fi
	@current_json=$$(gcloud secrets versions access latest \
		--project "$(DEPLOY_PROJECT_ID)" \
		--secret "$(DEPLOY_APP_CONFIG_SECRET_ID)" 2>/dev/null || echo "{}"); \
	if ! printf '%s' "$$current_json" | jq -e 'type=="object"' >/dev/null; then \
		echo "Current secret payload is not a JSON object."; \
		exit 1; \
	fi; \
	updated_json="$$current_json"; \
		synced_count=0; \
		while IFS= read -r raw_line || [[ -n "$$raw_line" ]]; do \
			line="$${raw_line%$$'\r'}"; \
		if [[ "$$line" =~ ^[[:space:]]*# ]]; then \
			continue; \
		fi; \
		if [[ -z "$${line//[[:space:]]/}" ]]; then \
			continue; \
		fi; \
		if [[ "$$line" != *"="* ]]; then \
			continue; \
		fi; \
			key="$${line%%=*}"; \
			value="$${line#*=}"; \
			key="$${key#"$${key%%[![:space:]]*}"}"; \
			key="$${key%"$${key##*[![:space:]]}"}"; \
		if [[ " $(APP_CONFIG_SYNC_KEYS) " != *" $$key "* ]]; then \
			continue; \
		fi; \
		if [[ "$$value" == \"*\" && "$$value" == *\" ]]; then \
			value="$${value:1:-1}"; \
		elif [[ "$$value" == \'*\' && "$$value" == *\' ]]; then \
			value="$${value:1:-1}"; \
		fi; \
		updated_json=$$(printf '%s' "$$updated_json" \
			| jq --arg key "$$key" --arg value "$$value" '.[$$key] = $$value'); \
		synced_count=$$((synced_count + 1)); \
	done < "$(APP_CONFIG_ENV_FILE)"; \
	if [[ $$synced_count -eq 0 ]]; then \
		echo "No allowed keys found in $(APP_CONFIG_ENV_FILE)."; \
		echo "Allowed keys: $(APP_CONFIG_SYNC_KEYS)"; \
		exit 1; \
	fi; \
	printf '%s' "$$updated_json" | gcloud secrets versions add "$(DEPLOY_APP_CONFIG_SECRET_ID)" \
		--project "$(DEPLOY_PROJECT_ID)" \
		--data-file=- >/dev/null; \
	echo "Synced $$synced_count keys from $(APP_CONFIG_ENV_FILE) to secret $(DEPLOY_APP_CONFIG_SECRET_ID)."; \
	if [[ "$(APP_CONFIG_PRUNE_ENV)" == "true" ]]; then \
		tmp_env_file=$$(mktemp); \
		keys_regex=$$(printf '%s' "$(APP_CONFIG_SYNC_KEYS)" | tr ' ' '|'); \
		awk -v keys_regex="^($$keys_regex)=" '\
			/^[[:space:]]*#/ { print; next } \
			/^[[:space:]]*$$/ { print; next } \
			$$0 ~ keys_regex { next } \
			{ print } \
		' "$(APP_CONFIG_ENV_FILE)" > "$$tmp_env_file"; \
		mv "$$tmp_env_file" "$(APP_CONFIG_ENV_FILE)"; \
		echo "Pruned synced keys from $(APP_CONFIG_ENV_FILE)."; \
	fi

simulate-whatsapp-message:
	@command -v jq >/dev/null 2>&1 || { echo "jq is required. Install with: brew install jq"; exit 1; }
	@echo "Using API_BASE=$(API_BASE) OWNER_EMAIL=$(OWNER_EMAIL)"
	@mkdir -p "$(FLOW_DIR)"; \
	login_response=$$(curl -sS -X POST "$(API_BASE)/v1/auth/login" \
		-H "Content-Type: application/json" \
		-d '{"email":"$(OWNER_EMAIL)","password":"$(OWNER_PASSWORD)"}'); \
	access_token=$$(echo "$$login_response" | jq -r '.access_token'); \
	if [[ "$$access_token" == "null" || -z "$$access_token" ]]; then \
		echo "Login failed (needed to run simulation). Response:"; \
		echo "$$login_response" | jq . 2>/dev/null || echo "$$login_response"; \
		exit 1; \
	fi; \
	echo "$$access_token" > "$(FLOW_DIR)/access_token"; \
	connection_response=$$(curl -sS "$(API_BASE)/v1/whatsapp/connection" \
		-H "Authorization: Bearer $$access_token"); \
	tenant_id=$$(echo "$$connection_response" | jq -r '.tenant_id'); \
	connection_status=$$(echo "$$connection_response" | jq -r '.status'); \
	phone_number_id=$$(echo "$$connection_response" | jq -r '.phone_number_id'); \
	if [[ "$$connection_status" != "CONNECTED" || "$$phone_number_id" == "null" || -z "$$phone_number_id" ]]; then \
		echo "WhatsApp connection is not ready. Response:"; \
		echo "$$connection_response" | jq . 2>/dev/null || echo "$$connection_response"; \
		echo ""; \
		echo "Hint: you are logged into tenant=$$tenant_id with OWNER_EMAIL=$(OWNER_EMAIL)."; \
		echo "If your UI shows another tenant as CONNECTED, you're using a different account or backend."; \
		echo "Run OAuth for this same account:"; \
		echo "make oauth-flow OWNER_EMAIL='$(OWNER_EMAIL)' OWNER_PASSWORD='$(OWNER_PASSWORD)' API_BASE='$(API_BASE)'"; \
		exit 1; \
	fi; \
	provider_message_id="$(SIM_PROVIDER_MESSAGE_ID)"; \
	if [[ -z "$$provider_message_id" ]]; then \
		provider_message_id="wamid.mock.$$(date +%s).$$RANDOM"; \
	fi; \
	payload=$$(jq -n \
		--arg phone_number_id "$$phone_number_id" \
		--arg wa_user_id "$(SIM_WA_USER_ID)" \
		--arg wa_user_name "$(SIM_WA_USER_NAME)" \
		--arg provider_message_id "$$provider_message_id" \
		--arg message_text "$(MESSAGE)" \
		'{ \
			object: "whatsapp_business_account", \
			entry: [ \
				{ \
					id: "mock_entry", \
					changes: [ \
						{ \
							field: "messages", \
							value: { \
								metadata: { phone_number_id: $$phone_number_id }, \
								contacts: [ \
									{ wa_id: $$wa_user_id, profile: { name: $$wa_user_name } } \
								], \
								messages: [ \
									{ \
										from: $$wa_user_id, \
										id: $$provider_message_id, \
										type: "text", \
										text: { body: $$message_text } \
									} \
								] \
							} \
						} \
					] \
				} \
			] \
		}'); \
	webhook_result=$$(curl -sS -w "\n%{http_code}" -X POST "$(API_BASE)/v1/webhooks/whatsapp" \
		-H "Content-Type: application/json" \
		-d "$$payload"); \
	webhook_http_code=$$(echo "$$webhook_result" | tail -n 1); \
	webhook_body=$$(echo "$$webhook_result" | sed '$$d'); \
	echo "Webhook HTTP status: $$webhook_http_code"; \
	echo "$$webhook_body" | jq . 2>/dev/null || echo "$$webhook_body"; \
	if [[ "$$webhook_http_code" == "502" ]]; then \
		echo ""; \
		echo "LLM provider failed, so no assistant message will be created for this simulation."; \
		echo "Check backend env vars: ANTHROPIC_API_KEY and ANTHROPIC_MODEL, then restart backend."; \
	fi; \
	if [[ "$$webhook_http_code" != "200" && "$$webhook_http_code" != "502" ]]; then \
		echo "Unexpected webhook status: $$webhook_http_code"; \
		exit 1; \
	fi; \
	conversations_response=$$(curl -sS "$(API_BASE)/v1/conversations" \
		-H "Authorization: Bearer $$access_token"); \
	conversation_id=$$(echo "$$conversations_response" | jq -r \
		--arg wa_user_id "$(SIM_WA_USER_ID)" \
		'.items[] | select(.whatsapp_user_id == $$wa_user_id) | .conversation_id' | head -n 1); \
	if [[ -z "$$conversation_id" || "$$conversation_id" == "null" ]]; then \
		echo "Conversation was not found for wa_user_id=$(SIM_WA_USER_ID)."; \
		echo "Conversations response:"; \
		echo "$$conversations_response" | jq . 2>/dev/null || echo "$$conversations_response"; \
		exit 1; \
	fi; \
	echo "Conversation ID: $$conversation_id"; \
	messages_response=$$(curl -sS "$(API_BASE)/v1/conversations/$$conversation_id/messages" \
		-H "Authorization: Bearer $$access_token"); \
	echo "Messages:"; \
	echo "$$messages_response" | jq . 2>/dev/null || echo "$$messages_response"
