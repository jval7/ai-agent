import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.manual_appointment_dto as manual_appointment_dto

router = fastapi.APIRouter(prefix="/v1/manual-appointments", tags=["manual_appointments"])


@router.get("", response_model=manual_appointment_dto.ManualAppointmentListResponseDTO)
def list_manual_appointments(
    status: str | None = None,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> manual_appointment_dto.ManualAppointmentListResponseDTO:
    return container.manual_appointment_service.list_appointments(claims, status)


@router.post("", response_model=manual_appointment_dto.ManualAppointmentDTO)
def create_manual_appointment(
    create_dto: manual_appointment_dto.CreateManualAppointmentDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> manual_appointment_dto.ManualAppointmentDTO:
    return container.manual_appointment_service.create_appointment(claims, create_dto)


@router.put(
    "/{appointment_id}/reschedule", response_model=manual_appointment_dto.ManualAppointmentDTO
)
def reschedule_manual_appointment(
    appointment_id: str,
    input_dto: manual_appointment_dto.RescheduleManualAppointmentDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> manual_appointment_dto.ManualAppointmentDTO:
    return container.manual_appointment_service.reschedule_appointment(
        claims=claims,
        appointment_id=appointment_id,
        input_dto=input_dto,
    )


@router.delete("/{appointment_id}", response_model=manual_appointment_dto.ManualAppointmentDTO)
def cancel_manual_appointment(
    appointment_id: str,
    input_dto: manual_appointment_dto.CancelManualAppointmentDTO | None = fastapi.Body(
        default=None
    ),
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> manual_appointment_dto.ManualAppointmentDTO:
    resolved_input_dto = (
        input_dto
        if input_dto is not None
        else manual_appointment_dto.CancelManualAppointmentDTO(reason=None)
    )
    return container.manual_appointment_service.cancel_appointment(
        claims=claims,
        appointment_id=appointment_id,
        input_dto=resolved_input_dto,
    )
