import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.onboarding_dto as onboarding_dto

router = fastapi.APIRouter(prefix="/v1/onboarding", tags=["onboarding"])


@router.get("/status", response_model=onboarding_dto.OnboardingStatusResponseDTO)
def get_onboarding_status(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> onboarding_dto.OnboardingStatusResponseDTO:
    return container.onboarding_status_service.get_status(claims.tenant_id)
