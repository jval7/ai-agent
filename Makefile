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
FRONTEND_DIR ?= frontend
SIM_WA_USER_ID ?= 573001234567
SIM_WA_USER_NAME ?= Cliente Demo
MESSAGE ?= Hola desde WhatsApp
SIM_PROVIDER_MESSAGE_ID ?=

.PHONY: \
	oauth-flow \
	memory-reset \
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
	simulate-whatsapp-message

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
