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
    meta_api_version: str
    anthropic_api_key: str
    anthropic_model: str
    anthropic_api_version: str
    anthropic_max_tokens: int
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
                "You are a helpful WhatsApp customer support agent.",
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
            meta_api_version=os.getenv("META_API_VERSION", "v23.0"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            anthropic_api_version=os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"),
            anthropic_max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "512")),
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
