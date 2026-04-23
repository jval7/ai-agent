import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.whatsapp_billing_dto as whatsapp_billing_dto

router = fastapi.APIRouter(prefix="/v1/whatsapp/billing", tags=["whatsapp-billing"])


@router.post(
    "/preflight",
    response_model=whatsapp_billing_dto.BillingPreflightResponseDTO,
    status_code=200,
)
def run_preflight(
    request: whatsapp_billing_dto.BillingPreflightRequestDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_billing_dto.BillingPreflightResponseDTO:
    return container.whatsapp_billing_service.run_preflight(claims.tenant_id, request)
