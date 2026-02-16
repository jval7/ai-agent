import fastapi
import fastapi.responses as fastapi_responses

import src.infra.logs as app_logs
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


def _build_json_response(
    request: fastapi.Request,
    status_code: int,
    content: dict[str, str],
) -> fastapi_responses.JSONResponse:
    response = fastapi_responses.JSONResponse(status_code=status_code, content=content)
    request_id = app_logs.get_request_id()
    if request_id is not None:
        response.headers[app_logs.REQUEST_ID_HEADER] = request_id
    return response


def register_exception_handlers(app: fastapi.FastAPI) -> None:
    @app.exception_handler(service_exceptions.AuthenticationError)
    async def handle_authentication_error(
        request: fastapi.Request,
        error: service_exceptions.AuthenticationError,
    ) -> fastapi_responses.JSONResponse:
        return _build_json_response(
            request=request,
            status_code=401,
            content={"detail": str(error)},
        )

    @app.exception_handler(service_exceptions.AuthorizationError)
    async def handle_authorization_error(
        request: fastapi.Request,
        error: service_exceptions.AuthorizationError,
    ) -> fastapi_responses.JSONResponse:
        return _build_json_response(
            request=request,
            status_code=403,
            content={"detail": str(error)},
        )

    @app.exception_handler(service_exceptions.EntityNotFoundError)
    async def handle_not_found_error(
        request: fastapi.Request,
        error: service_exceptions.EntityNotFoundError,
    ) -> fastapi_responses.JSONResponse:
        return _build_json_response(
            request=request,
            status_code=404,
            content={"detail": str(error)},
        )

    @app.exception_handler(service_exceptions.InvalidStateError)
    async def handle_invalid_state_error(
        request: fastapi.Request,
        error: service_exceptions.InvalidStateError,
    ) -> fastapi_responses.JSONResponse:
        return _build_json_response(
            request=request,
            status_code=400,
            content={"detail": str(error)},
        )

    @app.exception_handler(service_exceptions.DuplicateWebhookEventError)
    async def handle_duplicate_webhook_error(
        request: fastapi.Request,
        error: service_exceptions.DuplicateWebhookEventError,
    ) -> fastapi_responses.JSONResponse:
        return _build_json_response(
            request=request,
            status_code=409,
            content={"detail": str(error)},
        )

    @app.exception_handler(service_exceptions.ExternalProviderError)
    async def handle_external_provider_error(
        request: fastapi.Request,
        error: service_exceptions.ExternalProviderError,
    ) -> fastapi_responses.JSONResponse:
        return _build_json_response(
            request=request,
            status_code=502,
            content={"detail": str(error)},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_error(
        request: fastapi.Request,
        error: Exception,
    ) -> fastapi_responses.JSONResponse:
        request_id = app_logs.get_request_id()
        if request_id is None:
            request_id = "unknown"

        logger.exception(
            "http.unhandled_error",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="http.unhandled_error",
                    message="unhandled exception",
                    data={
                        "path": request.url.path,
                        "method": request.method,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                    },
                )
            },
        )
        response = _build_json_response(
            request=request,
            status_code=500,
            content={
                "detail": "internal server error",
                "request_id": request_id,
            },
        )
        app_logs.clear_request_context()
        return response
