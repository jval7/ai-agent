import fastapi
import fastapi.responses as fastapi_responses
import slowapi
import slowapi.errors as slowapi_errors
import slowapi.middleware as slowapi_middleware
import slowapi.util as slowapi_util

import src.infra.logs as app_logs

limiter = slowapi.Limiter(key_func=slowapi_util.get_remote_address)


def configure_rate_limiter(app: fastapi.FastAPI) -> None:
    app.state.limiter = limiter
    app.add_middleware(slowapi_middleware.SlowAPIMiddleware)
    app.add_exception_handler(
        slowapi_errors.RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )


async def _rate_limit_exceeded_handler(
    request: fastapi.Request,
    exc: slowapi_errors.RateLimitExceeded,
) -> fastapi_responses.JSONResponse:
    request_id = app_logs.get_request_id()
    return fastapi_responses.JSONResponse(
        status_code=429,
        content={"detail": "rate limit exceeded"},
        headers={"X-Request-Id": request_id} if request_id else {},
    )
