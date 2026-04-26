import asyncio
import json
import typing

import fastapi
import fastapi.responses as fastapi_responses

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto

router = fastapi.APIRouter(prefix="/v1/events", tags=["events"])

KEEPALIVE_INTERVAL_SECONDS = 25.0


def _format_event(event_type: str, payload: dict[str, str]) -> str:
    data_line = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data_line}\n\n"


@router.get("")
async def stream_events(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> fastapi_responses.StreamingResponse:
    tenant_id = claims.tenant_id

    async def generator() -> typing.AsyncIterator[str]:
        subscription = container.event_stream_service.subscribe(tenant_id)
        try:
            yield _format_event("connected", {"tenant_id": tenant_id})
            while True:
                try:
                    event = await asyncio.wait_for(
                        subscription.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SECONDS,
                    )
                    yield _format_event(event.type, event.payload)
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            subscription.teardown()

    return fastapi_responses.StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
