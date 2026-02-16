import contextvars
import datetime
import json
import logging
import logging.config

REQUEST_ID_HEADER = "X-Request-ID"

_REQUEST_ID_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)
_TENANT_ID_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id",
    default=None,
)
_USER_ID_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_id",
    default=None,
)

_SENSITIVE_EXACT_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "secret",
    "code",
}
_SENSITIVE_SUFFIXES = (
    "_token",
    "_secret",
    "_api_key",
    "_password",
    "_password_hash",
    "_code",
)
_NON_SENSITIVE_CODE_KEYS = {
    "status_code",
    "error_code",
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event_payload: dict[str, object] = {}
        raw_event_payload = record.__dict__.get("event_data")
        if isinstance(raw_event_payload, dict):
            event_payload = sanitize_log_data(raw_event_payload)

        message_value = event_payload.get("message")
        if not isinstance(message_value, str) or not message_value:
            event_payload["message"] = record.getMessage()

        event_value = event_payload.get("event")
        if not isinstance(event_value, str) or not event_value:
            event_payload["event"] = record.getMessage()

        if "request_id" not in event_payload:
            event_payload["request_id"] = get_request_id()
        if "tenant_id" not in event_payload:
            event_payload["tenant_id"] = _TENANT_ID_CONTEXT.get()
        if "user_id" not in event_payload:
            event_payload["user_id"] = _USER_ID_CONTEXT.get()

        event_payload["timestamp"] = (
            datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        )
        event_payload["level"] = record.levelname
        event_payload["logger"] = record.name

        if record.exc_info is not None:
            exc_type = record.exc_info[0]
            event_payload["error_type"] = "Exception"
            if exc_type is not None:
                event_payload["error_type"] = exc_type.__name__
            event_payload["traceback"] = self.formatException(record.exc_info)

        return json.dumps(event_payload, ensure_ascii=True, separators=(",", ":"))


def configure_logging(log_level: str) -> None:
    normalized_log_level = log_level.strip().upper()
    if not normalized_log_level:
        normalized_log_level = "INFO"

    config: dict[str, object] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "src.infra.logs.JsonLogFormatter",
            }
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {
            "handlers": ["stdout"],
            "level": normalized_log_level,
        },
        "loggers": {
            "uvicorn.access": {
                "handlers": ["stdout"],
                "level": "WARNING",
                "propagate": False,
            },
            "httpx": {
                "handlers": ["stdout"],
                "level": "WARNING",
                "propagate": False,
            },
            "httpcore": {
                "handlers": ["stdout"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_context(
    request_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> None:
    _REQUEST_ID_CONTEXT.set(request_id)
    _TENANT_ID_CONTEXT.set(tenant_id)
    _USER_ID_CONTEXT.set(user_id)


def set_authenticated_context(tenant_id: str, user_id: str) -> None:
    _TENANT_ID_CONTEXT.set(tenant_id)
    _USER_ID_CONTEXT.set(user_id)


def clear_request_context() -> None:
    _REQUEST_ID_CONTEXT.set(None)
    _TENANT_ID_CONTEXT.set(None)
    _USER_ID_CONTEXT.set(None)


def get_request_id() -> str | None:
    return _REQUEST_ID_CONTEXT.get()


def build_log_event(
    event_name: str,
    message: str,
    data: dict[str, object] | None = None,
) -> dict[str, object]:
    event_data: dict[str, object] = {
        "event": event_name,
        "message": message,
        "request_id": _REQUEST_ID_CONTEXT.get(),
        "tenant_id": _TENANT_ID_CONTEXT.get(),
        "user_id": _USER_ID_CONTEXT.get(),
    }
    if data is None:
        return event_data

    sanitized_data = sanitize_log_data(data)
    for key, value in sanitized_data.items():
        event_data[key] = value
    return event_data


def sanitize_log_data(data: dict[str, object]) -> dict[str, object]:
    sanitized_data: dict[str, object] = {}
    for key, value in data.items():
        normalized_key = key.lower()
        if _is_sensitive_key(normalized_key):
            sanitized_data[key] = "[REDACTED]"
            continue
        sanitized_data[key] = _sanitize_value(value)
    return sanitized_data


def _sanitize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        sanitized_list_items: list[object] = []
        for item in value:
            sanitized_list_items.append(_sanitize_value(item))
        return sanitized_list_items
    if isinstance(value, tuple):
        sanitized_tuple_items: list[object] = []
        for item in value:
            sanitized_tuple_items.append(_sanitize_value(item))
        return sanitized_tuple_items
    if isinstance(value, dict):
        sanitized_dict_items: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            normalized_key = key.lower()
            if _is_sensitive_key(normalized_key):
                sanitized_dict_items[key] = "[REDACTED]"
                continue
            sanitized_dict_items[key] = _sanitize_value(raw_value)
        return sanitized_dict_items
    return str(value)


def _is_sensitive_key(normalized_key: str) -> bool:
    if normalized_key in _NON_SENSITIVE_CODE_KEYS:
        return False
    if normalized_key in _SENSITIVE_EXACT_KEYS:
        return True
    return any(normalized_key.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)
