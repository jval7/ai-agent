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
    "/v1/conversations/{conversation_id}/scheduling/requests/{request_id}/consultation-review",
    response_model=scheduling_dto.ConsultationReviewDecisionResponseDTO,
)
def resolve_consultation_review(
    conversation_id: str,
    request_id: str,
    review_dto: scheduling_dto.ConsultationReviewDecisionDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.ConsultationReviewDecisionResponseDTO:
    return container.scheduling_inbox_service.resolve_consultation_review(
        claims=claims,
        conversation_id=conversation_id,
        request_id=request_id,
        input_dto=review_dto,
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


@router.put(
    "/v1/scheduling-requests/{request_id}/booked-slot/reschedule",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def reschedule_booked_slot(
    request_id: str,
    input_dto: scheduling_dto.RescheduleBookedSlotInputDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    if claims.role != service_constants.DEFAULT_OWNER_ROLE:
        raise service_exceptions.AuthorizationError("owner role required")
    return container.scheduling_service.reschedule_booked_slot(
        tenant_id=claims.tenant_id,
        request_id=request_id,
        input_dto=input_dto,
    )


@router.delete(
    "/v1/scheduling-requests/{request_id}/booked-slot",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def cancel_booked_slot(
    request_id: str,
    input_dto: scheduling_dto.CancelBookedSlotInputDTO | None = fastapi.Body(default=None),
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    if claims.role != service_constants.DEFAULT_OWNER_ROLE:
        raise service_exceptions.AuthorizationError("owner role required")
    resolved_input_dto = (
        input_dto if input_dto is not None else scheduling_dto.CancelBookedSlotInputDTO(reason=None)
    )
    return container.scheduling_service.cancel_booked_slot(
        tenant_id=claims.tenant_id,
        request_id=request_id,
        input_dto=resolved_input_dto,
    )


@router.put(
    "/v1/scheduling-requests/{request_id}/booked-slot/payment",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def update_booked_slot_payment(
    request_id: str,
    input_dto: scheduling_dto.UpdateBookedSlotPaymentInputDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    if claims.role != service_constants.DEFAULT_OWNER_ROLE:
        raise service_exceptions.AuthorizationError("owner role required")
    return container.scheduling_service.update_booked_payment(
        tenant_id=claims.tenant_id,
        request_id=request_id,
        input_dto=input_dto,
    )
