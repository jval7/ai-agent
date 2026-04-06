import fastapi
import fastapi.responses as fastapi_responses

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.rate_limiter as rate_limiter
import src.infra.container as app_container
import src.services.dto.webhook_dto as webhook_dto

router = fastapi.APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.get("/whatsapp", response_class=fastapi_responses.PlainTextResponse)
@rate_limiter.limiter.limit("30/minute")  # type: ignore[misc]
def verify_whatsapp_webhook(
    request: fastapi.Request,
    mode: str = fastapi.Query(alias="hub.mode"),
    verify_token: str = fastapi.Query(alias="hub.verify_token"),
    challenge: str = fastapi.Query(alias="hub.challenge"),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> str:
    verification_dto = webhook_dto.WebhookVerificationDTO(
        mode=mode,
        verify_token=verify_token,
        challenge=challenge,
    )
    return container.whatsapp_onboarding_service.verify_webhook(verification_dto)


@router.post("/whatsapp", response_model=webhook_dto.WebhookEventResponseDTO)
@rate_limiter.limiter.limit("120/minute")  # type: ignore[misc]
def receive_whatsapp_webhook(
    request: fastapi.Request,
    payload: dict[str, object],
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> webhook_dto.WebhookEventResponseDTO:
    return container.webhook_service.process_payload(payload)
