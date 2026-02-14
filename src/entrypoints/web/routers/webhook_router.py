import fastapi
import fastapi.responses as fastapi_responses

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.webhook_dto as webhook_dto

router = fastapi.APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.get("/whatsapp", response_class=fastapi_responses.PlainTextResponse)
def verify_whatsapp_webhook(
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
def receive_whatsapp_webhook(
    payload: dict[str, object],
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> webhook_dto.WebhookEventResponseDTO:
    return container.webhook_service.process_payload(payload)
