import time
import typing
import uuid

import fastapi
import starlette.middleware.base as starlette_base

import src.infra.logs as app_logs

logger = app_logs.get_logger(__name__)


class RequestContextMiddleware(starlette_base.BaseHTTPMiddleware):
    def __init__(
        self,
        app: typing.Any,
        include_request_summary: bool,
    ) -> None:
        super().__init__(app)
        self._include_request_summary = include_request_summary

    async def dispatch(
        self,
        request: fastapi.Request,
        call_next: typing.Callable[[fastapi.Request], typing.Awaitable[fastapi.Response]],
    ) -> fastapi.Response:
        request_id = _resolve_request_id(
            request.headers.get(app_logs.REQUEST_ID_HEADER),
        )
        app_logs.set_request_context(request_id=request_id)
        request.state.request_id = request_id

        request_started_at = time.perf_counter()
        response = await call_next(request)
        request_duration_ms = int((time.perf_counter() - request_started_at) * 1000)

        response.headers[app_logs.REQUEST_ID_HEADER] = request_id

        if self._include_request_summary:
            logger.info(
                "http.request.completed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="http.request.completed",
                        message="http request completed",
                        data={
                            "path": request.url.path,
                            "method": request.method,
                            "status_code": response.status_code,
                            "duration_ms": request_duration_ms,
                        },
                    )
                },
            )

        app_logs.clear_request_context()
        return response


def _resolve_request_id(raw_request_id: str | None) -> str:
    if raw_request_id is None:
        return str(uuid.uuid4())

    normalized_request_id = raw_request_id.strip()
    if not normalized_request_id:
        return str(uuid.uuid4())

    return normalized_request_id
