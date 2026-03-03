import os

import pydantic


class Settings(pydantic.BaseModel):
    jwt_secret: str
    jwt_access_ttl_seconds: int
    jwt_refresh_ttl_seconds: int
    default_system_prompt: str
    conversation_context_messages: int
    memory_json_file_path: str | None
    cors_allowed_origins: list[str]
    frontend_app_base_url: str
    enable_dev_endpoints: bool
    meta_app_id: str
    meta_app_secret: str
    meta_redirect_uri: str
    meta_webhook_verify_token: str
    meta_phone_registration_pin: str
    meta_api_version: str
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str
    gemini_project_id: str
    gemini_location: str
    gemini_model: str
    gemini_max_output_tokens: int
    langsmith_tracing_enabled: bool
    langsmith_project: str
    langsmith_api_key: str | None
    langsmith_endpoint: str | None
    langsmith_workspace_id: str | None
    langsmith_environment: str | None
    langsmith_tags: list[str]
    log_level: str
    log_include_request_summary: bool

    @classmethod
    def from_env(cls) -> "Settings":
        memory_json_file_path = os.getenv("MEMORY_JSON_FILE_PATH", "data/memory_store.json")
        normalized_memory_json_file_path = memory_json_file_path.strip() or None
        cors_allowed_origins = cls._parse_csv_env(
            os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
        )

        return cls(
            jwt_secret=os.getenv("JWT_SECRET", "dev-secret-change-me"),
            jwt_access_ttl_seconds=int(os.getenv("JWT_ACCESS_TTL_SECONDS", "1800")),
            jwt_refresh_ttl_seconds=int(os.getenv("JWT_REFRESH_TTL_SECONDS", "2592000")),
            default_system_prompt=os.getenv(
                "DEFAULT_SYSTEM_PROMPT",
                (
                    "Eres un asistente de WhatsApp para agendar sesiones. "
                    "Debes saludar, presentarte brevemente y guiar al paciente en un tono natural y empatico. "
                    "Pide la informacion de forma progresiva, un dato por mensaje, nunca en bloque. "
                    "No suenes robotico ni menciones procesos internos, revisiones o validaciones. "
                    "Si necesitas tiempo, usa frases naturales como: 'Dame un momento y reviso disponibilidad'."
                ),
            ),
            conversation_context_messages=int(os.getenv("CONTEXT_MESSAGE_LIMIT", "12")),
            memory_json_file_path=normalized_memory_json_file_path,
            cors_allowed_origins=cors_allowed_origins,
            frontend_app_base_url=os.getenv("FRONTEND_APP_BASE_URL", "http://localhost:5173"),
            enable_dev_endpoints=os.getenv("ENABLE_DEV_ENDPOINTS", "true").lower() == "true",
            meta_app_id=os.getenv("META_APP_ID", ""),
            meta_app_secret=os.getenv("META_APP_SECRET", ""),
            meta_redirect_uri=os.getenv("META_REDIRECT_URI", ""),
            meta_webhook_verify_token=os.getenv(
                "META_WEBHOOK_VERIFY_TOKEN",
                "dev-meta-webhook-verify-token",
            ),
            meta_phone_registration_pin=os.getenv("META_PHONE_REGISTRATION_PIN", ""),
            meta_api_version=os.getenv("META_API_VERSION", "v23.0"),
            google_oauth_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            google_oauth_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            google_oauth_redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", ""),
            gemini_project_id=os.getenv("GEMINI_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", "")),
            gemini_location=os.getenv(
                "GEMINI_LOCATION",
                os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            ),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "512")),
            langsmith_tracing_enabled=os.getenv("LANGSMITH_TRACING_ENABLED", "false").lower()
            == "true",
            langsmith_project=os.getenv("LANGSMITH_PROJECT", "ai-agent-dev"),
            langsmith_api_key=cls._normalize_optional_text(
                os.getenv("LANGSMITH_API_KEY", os.getenv("LANGCHAIN_API_KEY", ""))
            ),
            langsmith_endpoint=cls._normalize_optional_text(
                os.getenv("LANGSMITH_ENDPOINT", os.getenv("LANGCHAIN_ENDPOINT", ""))
            ),
            langsmith_workspace_id=cls._normalize_optional_text(
                os.getenv("LANGSMITH_WORKSPACE_ID", "")
            ),
            langsmith_environment=cls._normalize_optional_text(
                os.getenv("LANGSMITH_ENVIRONMENT", "local")
            ),
            langsmith_tags=cls._parse_csv_env(os.getenv("LANGSMITH_TAGS", "ai-agent")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_include_request_summary=os.getenv(
                "LOG_INCLUDE_REQUEST_SUMMARY",
                "false",
            ).lower()
            == "true",
        )

    @staticmethod
    def _parse_csv_env(raw_value: str) -> list[str]:
        parsed_items: list[str] = []
        for raw_item in raw_value.split(","):
            normalized_item = raw_item.strip()
            if normalized_item:
                parsed_items.append(normalized_item)
        return parsed_items

    @staticmethod
    def _normalize_optional_text(raw_value: str) -> str | None:
        normalized_value = raw_value.strip()
        if normalized_value:
            return normalized_value
        return None
