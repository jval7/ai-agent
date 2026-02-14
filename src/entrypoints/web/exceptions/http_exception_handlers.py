import fastapi
import fastapi.responses as fastapi_responses

import src.services.exceptions as service_exceptions


def register_exception_handlers(app: fastapi.FastAPI) -> None:
    @app.exception_handler(service_exceptions.AuthenticationError)
    async def handle_authentication_error(
        _request: fastapi.Request,
        error: service_exceptions.AuthenticationError,
    ) -> fastapi_responses.JSONResponse:
        return fastapi_responses.JSONResponse(status_code=401, content={"detail": str(error)})

    @app.exception_handler(service_exceptions.AuthorizationError)
    async def handle_authorization_error(
        _request: fastapi.Request,
        error: service_exceptions.AuthorizationError,
    ) -> fastapi_responses.JSONResponse:
        return fastapi_responses.JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(service_exceptions.EntityNotFoundError)
    async def handle_not_found_error(
        _request: fastapi.Request,
        error: service_exceptions.EntityNotFoundError,
    ) -> fastapi_responses.JSONResponse:
        return fastapi_responses.JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(service_exceptions.InvalidStateError)
    async def handle_invalid_state_error(
        _request: fastapi.Request,
        error: service_exceptions.InvalidStateError,
    ) -> fastapi_responses.JSONResponse:
        return fastapi_responses.JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(service_exceptions.DuplicateWebhookEventError)
    async def handle_duplicate_webhook_error(
        _request: fastapi.Request,
        error: service_exceptions.DuplicateWebhookEventError,
    ) -> fastapi_responses.JSONResponse:
        return fastapi_responses.JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(service_exceptions.ExternalProviderError)
    async def handle_external_provider_error(
        _request: fastapi.Request,
        error: service_exceptions.ExternalProviderError,
    ) -> fastapi_responses.JSONResponse:
        return fastapi_responses.JSONResponse(status_code=502, content={"detail": str(error)})
