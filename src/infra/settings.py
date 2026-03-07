import json
import os

import pydantic

_CORS_ALLOWED_ORIGINS_OVERRIDE_ENV_VAR = "CORS_ALLOWED_ORIGINS_OVERRIDE"


class Settings(pydantic.BaseModel):
    jwt_secret: str
    jwt_access_ttl_seconds: int
    jwt_refresh_ttl_seconds: int
    default_system_prompt: str
    conversation_context_messages: int
    firestore_database_id: str
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
    google_cloud_project_id: str
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
    def from_secret_json(cls, raw_app_config_json: str, adc_project_id: str) -> "Settings":
        app_config_overrides = cls._parse_app_config_overrides(raw_app_config_json)
        resolved_project_id = cls._resolve_google_cloud_project_id(
            adc_project_id=adc_project_id,
            app_config_overrides=app_config_overrides,
        )
        cors_allowed_origins = cls._resolve_cors_allowed_origins(app_config_overrides)
        firestore_database_id = app_config_overrides.get(
            "FIRESTORE_DATABASE_ID", "(default)"
        ).strip()
        normalized_firestore_database_id = firestore_database_id or "(default)"

        return cls(
            jwt_secret=cls._resolve_required_secret(app_config_overrides, "JWT_SECRET"),
            jwt_access_ttl_seconds=int(app_config_overrides.get("JWT_ACCESS_TTL_SECONDS", "1800")),
            jwt_refresh_ttl_seconds=int(
                app_config_overrides.get("JWT_REFRESH_TTL_SECONDS", "2592000")
            ),
            default_system_prompt=app_config_overrides.get(
                "DEFAULT_SYSTEM_PROMPT",
                (
                    "Eres un asistente de WhatsApp para agendar sesiones. "
                    "Debes saludar, presentarte brevemente y guiar al paciente en un tono natural y empatico. "
                    "Pide la informacion de forma progresiva; en confirmacion, pide todos los datos juntos. "
                    "No suenes robotico ni menciones procesos internos, revisiones o validaciones. "
                    "Si necesitas tiempo, usa frases naturales como: 'Dame un momento y reviso disponibilidad'."
                ),
            ),
            conversation_context_messages=int(
                app_config_overrides.get("CONTEXT_MESSAGE_LIMIT", "12")
            ),
            firestore_database_id=normalized_firestore_database_id,
            cors_allowed_origins=cors_allowed_origins,
            frontend_app_base_url=app_config_overrides.get(
                "FRONTEND_APP_BASE_URL",
                "http://localhost:5173",
            ),
            enable_dev_endpoints=app_config_overrides.get("ENABLE_DEV_ENDPOINTS", "true").lower()
            == "true",
            meta_app_id=app_config_overrides.get("META_APP_ID", ""),
            meta_app_secret=app_config_overrides.get("META_APP_SECRET", ""),
            meta_redirect_uri=app_config_overrides.get("META_REDIRECT_URI", ""),
            meta_webhook_verify_token=app_config_overrides.get(
                "META_WEBHOOK_VERIFY_TOKEN",
                "dev-meta-webhook-verify-token",
            ),
            meta_phone_registration_pin=app_config_overrides.get("META_PHONE_REGISTRATION_PIN", ""),
            meta_api_version=app_config_overrides.get("META_API_VERSION", "v23.0"),
            google_oauth_client_id=app_config_overrides.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            google_oauth_client_secret=app_config_overrides.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            google_oauth_redirect_uri=app_config_overrides.get("GOOGLE_OAUTH_REDIRECT_URI", ""),
            google_cloud_project_id=resolved_project_id,
            gemini_location=app_config_overrides.get(
                "GEMINI_LOCATION",
                app_config_overrides.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            ),
            gemini_model=app_config_overrides.get("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_max_output_tokens=int(
                app_config_overrides.get("GEMINI_MAX_OUTPUT_TOKENS", "512")
            ),
            langsmith_tracing_enabled=app_config_overrides.get(
                "LANGSMITH_TRACING_ENABLED",
                "false",
            ).lower()
            == "true",
            langsmith_project=app_config_overrides.get("LANGSMITH_PROJECT", "ai-agent-dev"),
            langsmith_api_key=cls._normalize_optional_text(
                app_config_overrides.get(
                    "LANGSMITH_API_KEY",
                    app_config_overrides.get("LANGCHAIN_API_KEY", ""),
                )
            ),
            langsmith_endpoint=cls._normalize_optional_text(
                app_config_overrides.get(
                    "LANGSMITH_ENDPOINT",
                    app_config_overrides.get("LANGCHAIN_ENDPOINT", ""),
                )
            ),
            langsmith_workspace_id=cls._normalize_optional_text(
                app_config_overrides.get("LANGSMITH_WORKSPACE_ID", "")
            ),
            langsmith_environment=cls._normalize_optional_text(
                app_config_overrides.get("LANGSMITH_ENVIRONMENT", "local")
            ),
            langsmith_tags=cls._parse_csv_env(
                app_config_overrides.get("LANGSMITH_TAGS", "ai-agent")
            ),
            log_level=app_config_overrides.get("LOG_LEVEL", "INFO"),
            log_include_request_summary=app_config_overrides.get(
                "LOG_INCLUDE_REQUEST_SUMMARY",
                "false",
            ).lower()
            == "true",
        )

    _INSECURE_DEV_DEFAULT = "dev-secret-change-me"

    @staticmethod
    def _resolve_required_secret(
        app_config_overrides: dict[str, str],
        key: str,
    ) -> str:
        dev_default = Settings._INSECURE_DEV_DEFAULT
        if not app_config_overrides:
            return dev_default
        value = app_config_overrides.get(key, "").strip()
        if value == "" or value == dev_default:
            raise ValueError(
                f"{key} is missing or still set to the insecure default. "
                f"Set it in the app config secret."
            )
        return value

    @staticmethod
    def _resolve_google_cloud_project_id(
        adc_project_id: str,
        app_config_overrides: dict[str, str],
    ) -> str:
        project_id_from_secret = app_config_overrides.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if project_id_from_secret != "":
            return project_id_from_secret

        normalized_adc_project_id = adc_project_id.strip()
        if normalized_adc_project_id == "":
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is missing in app config secret and ADC project is empty"
            )
        return normalized_adc_project_id

    @classmethod
    def _parse_app_config_overrides(cls, raw_app_config_json: str) -> dict[str, str]:
        normalized_raw_app_config_json = raw_app_config_json.strip()
        if normalized_raw_app_config_json == "":
            return {}

        try:
            parsed_app_config = json.loads(normalized_raw_app_config_json)
        except json.JSONDecodeError as error:
            raise ValueError("App config secret must be valid JSON") from error

        if not isinstance(parsed_app_config, dict):
            raise ValueError("App config secret must be a JSON object")

        overrides: dict[str, str] = {}
        for key, value in parsed_app_config.items():
            if not isinstance(key, str):
                raise ValueError("App config secret keys must be strings")

            normalized_key = key.strip()
            if normalized_key == "":
                raise ValueError("App config secret keys cannot be empty")

            overrides[normalized_key] = cls._serialize_app_config_value(value)

        return overrides

    @staticmethod
    def _serialize_app_config_value(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(value)
        if isinstance(value, list):
            serialized_items: list[str] = []
            for item in value:
                serialized_items.append(Settings._serialize_app_config_scalar(item))
            return ",".join(serialized_items)
        if isinstance(value, dict):
            return json.dumps(value, separators=(",", ":"))
        raise ValueError("App config secret contains unsupported value type")

    @staticmethod
    def _serialize_app_config_scalar(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(value)
        raise ValueError("App config secret arrays must contain scalar values")

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

    @classmethod
    def _resolve_cors_allowed_origins(
        cls,
        app_config_overrides: dict[str, str],
    ) -> list[str]:
        raw_override_value = os.getenv(_CORS_ALLOWED_ORIGINS_OVERRIDE_ENV_VAR, "")
        normalized_override_value = raw_override_value.strip()
        if normalized_override_value != "":
            return cls._parse_csv_env(normalized_override_value)
        return cls._parse_csv_env(
            app_config_overrides.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
        )
