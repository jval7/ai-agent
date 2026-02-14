import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.whatsapp_dto as whatsapp_dto

router = fastapi.APIRouter(prefix="/v1/whatsapp", tags=["whatsapp"])


@router.post(
    "/embedded-signup/session", response_model=whatsapp_dto.EmbeddedSignupSessionResponseDTO
)
def create_embedded_signup_session(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_dto.EmbeddedSignupSessionResponseDTO:
    return container.whatsapp_onboarding_service.create_embedded_signup_session(claims.tenant_id)


@router.post("/embedded-signup/complete", response_model=whatsapp_dto.WhatsappConnectionStatusDTO)
def complete_embedded_signup(
    complete_dto: whatsapp_dto.EmbeddedSignupCompleteDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_dto.WhatsappConnectionStatusDTO:
    return container.whatsapp_onboarding_service.complete_embedded_signup(
        claims.tenant_id, complete_dto
    )


@router.get("/connection", response_model=whatsapp_dto.WhatsappConnectionStatusDTO)
def get_connection_status(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_dto.WhatsappConnectionStatusDTO:
    return container.whatsapp_onboarding_service.get_connection_status(claims.tenant_id)


@router.get("/dev/verify-token", response_model=whatsapp_dto.DevVerifyTokenDTO)
def get_dev_verify_token(
    _claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_dto.DevVerifyTokenDTO:
    return container.whatsapp_onboarding_service.get_dev_verify_token()
