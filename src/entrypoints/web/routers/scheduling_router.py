import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions

router = fastapi.APIRouter(tags=["scheduling"])


@router.get(
    "/v1/scheduling-requests", response_model=scheduling_dto.SchedulingRequestListResponseDTO
)
def list_scheduling_requests(
    status: str | None = None,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.SchedulingRequestListResponseDTO:
    if claims.role != service_constants.DEFAULT_OWNER_ROLE:
        raise service_exceptions.AuthorizationError("owner role required")
    return container.scheduling_inbox_service.list_requests(
        tenant_id=claims.tenant_id,
        status=status,
    )


@router.get(
    "/v1/conversations/{conversation_id}/scheduling/requests",
    response_model=scheduling_dto.SchedulingRequestListResponseDTO,
)
def list_conversation_scheduling_requests(
    conversation_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.SchedulingRequestListResponseDTO:
    if claims.role != service_constants.DEFAULT_OWNER_ROLE:
        raise service_exceptions.AuthorizationError("owner role required")
    return container.scheduling_service.list_requests_by_conversation(
        tenant_id=claims.tenant_id,
        conversation_id=conversation_id,
    )


@router.post(
    "/v1/conversations/{conversation_id}/scheduling/requests/{request_id}/professional-slots",
    response_model=scheduling_dto.ProfessionalSubmitSlotsResponseDTO,
)
def submit_professional_slots(
    conversation_id: str,
    request_id: str,
    submit_dto: scheduling_dto.ProfessionalSubmitSlotsDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.ProfessionalSubmitSlotsResponseDTO:
    return container.scheduling_inbox_service.submit_professional_slots(
        claims=claims,
        conversation_id=conversation_id,
        request_id=request_id,
        submit_dto=submit_dto,
    )
