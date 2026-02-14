SHELL := /bin/zsh

ifneq (,$(wildcard .env))
include .env
export
endif

API_BASE ?= http://localhost:8000
TENANT_NAME ?= Acme
OWNER_EMAIL ?= owner@acme.com
OWNER_PASSWORD ?= supersecret
FLOW_DIR ?= .make-flow
MEMORY_JSON_FILE_PATH ?= data/memory_store.json

.PHONY: oauth-flow memory-reset static-checks

oauth-flow:
	@command -v jq >/dev/null 2>&1 || { echo "jq is required. Install with: brew install jq"; exit 1; }
	@mkdir -p "$(FLOW_DIR)"
	@register_response=$$(curl -sS -X POST "$(API_BASE)/v1/auth/register" \
		-H "Content-Type: application/json" \
		-d '{"tenant_name":"$(TENANT_NAME)","email":"$(OWNER_EMAIL)","password":"$(OWNER_PASSWORD)"}'); \
	access_token=$$(echo "$$register_response" | jq -r '.access_token'); \
	if [[ "$$access_token" == "null" || -z "$$access_token" ]]; then \
		echo "Register failed:"; \
		echo "$$register_response" | jq . 2>/dev/null || echo "$$register_response"; \
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

memory-reset:
	@if [[ -f "$(FLOW_DIR)/access_token" ]]; then \
		access_token=$$(cat "$(FLOW_DIR)/access_token"); \
		live_reset_response=$$(curl -sS -X POST "$(API_BASE)/v1/dev/memory/reset" \
			-H "Authorization: Bearer $$access_token" || true); \
		echo "Live reset response: $$live_reset_response"; \
	else \
		echo "No access token in $(FLOW_DIR)/access_token; skipping live reset endpoint."; \
	fi
	@if [[ -z "$(MEMORY_JSON_FILE_PATH)" ]]; then \
		echo "MEMORY_JSON_FILE_PATH is empty (persistence disabled). Nothing to delete."; \
		exit 0; \
	fi
	@if [[ -f "$(MEMORY_JSON_FILE_PATH)" ]]; then \
		rm -f "$(MEMORY_JSON_FILE_PATH)"; \
		echo "Deleted $(MEMORY_JSON_FILE_PATH)"; \
	else \
		echo "Memory file not found: $(MEMORY_JSON_FILE_PATH)"; \
	fi

static-checks:
	@uv run ruff check .
	@uv run ruff format --check .
	@uv run mypy src tests
	@uv run bandit -c pyproject.toml -r src
