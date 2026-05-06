import datetime
import logging

import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.admin_dto as admin_dto
import src.services.dto.agent_dto as agent_dto
import src.services.dto.auth_dto as auth_dto
import src.services.dto.blacklist_dto as blacklist_dto
import src.services.dto.conversation_dto as conversation_dto
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.manual_appointment_dto as manual_appointment_dto
import src.services.dto.patient_dto as patient_dto
import src.services.dto.scheduled_reminder_dto as scheduled_reminder_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.dto.tag_dto as tag_dto

admin_audit = logging.getLogger("admin_audit")

router = fastapi.APIRouter(prefix="/v1/admin", tags=["admin"])

_admin_dep = fastapi.Depends(http_dependencies.require_admin_claims)
_container_dep = fastapi.Depends(http_dependencies.get_container)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=admin_dto.GlobalMetricsDTO)
def get_global_metrics(
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> admin_dto.GlobalMetricsDTO:
    return container.admin_dashboard_service.get_global_metrics()


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


@router.get("/tenants", response_model=list[admin_dto.TenantSummaryDTO])
def list_tenants(
    search: str | None = fastapi.Query(default=None),
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> list[admin_dto.TenantSummaryDTO]:
    return container.admin_dashboard_service.list_tenant_summaries(search=search)


@router.get("/tenants/{tenant_id}", response_model=admin_dto.TenantSummaryDTO)
def get_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> admin_dto.TenantSummaryDTO:
    summary = container.admin_dashboard_service.get_tenant_summary(tenant_id)
    if summary is None:
        raise fastapi.HTTPException(status_code=404, detail="tenant not found")
    return summary


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/patients",
    response_model=patient_dto.PatientListResponseDTO,
)
def list_patients_for_tenant(
    tenant_id: str,
    search: str | None = fastapi.Query(default=None),
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> patient_dto.PatientListResponseDTO:
    return container.patient_query_service.list_patients_for_tenant(tenant_id, search=search)


@router.post(
    "/tenants/{tenant_id}/patients",
    response_model=patient_dto.PatientDTO,
    status_code=fastapi.status.HTTP_201_CREATED,
)
def create_patient_for_tenant(
    tenant_id: str,
    create_dto: patient_dto.CreatePatientDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> patient_dto.PatientDTO:
    admin_audit.info(
        "admin.patient.create",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
        },
    )
    return container.patient_query_service.create_patient_for_tenant(tenant_id, create_dto)


@router.get(
    "/tenants/{tenant_id}/patients/{whatsapp_user_id}",
    response_model=patient_dto.PatientDTO,
)
def get_patient_for_tenant(
    tenant_id: str,
    whatsapp_user_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> patient_dto.PatientDTO:
    return container.patient_query_service.get_patient_for_tenant(tenant_id, whatsapp_user_id)


@router.put(
    "/tenants/{tenant_id}/patients/{whatsapp_user_id}",
    response_model=patient_dto.PatientDTO,
)
def update_patient_for_tenant(
    tenant_id: str,
    whatsapp_user_id: str,
    update_dto: patient_dto.UpdatePatientDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> patient_dto.PatientDTO:
    admin_audit.info(
        "admin.patient.update",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "whatsapp_user_id": whatsapp_user_id,
        },
    )
    return container.patient_query_service.update_patient_for_tenant(
        tenant_id, whatsapp_user_id, update_dto
    )


@router.delete(
    "/tenants/{tenant_id}/patients/{whatsapp_user_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def delete_patient_for_tenant(
    tenant_id: str,
    whatsapp_user_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> None:
    admin_audit.info(
        "admin.patient.delete",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "whatsapp_user_id": whatsapp_user_id,
        },
    )
    container.patient_query_service.delete_patient_for_tenant(tenant_id, whatsapp_user_id)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/conversations",
    response_model=conversation_dto.ConversationListResponseDTO,
)
def list_conversations_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> conversation_dto.ConversationListResponseDTO:
    return container.conversation_query_service.list_conversations(tenant_id)


@router.get(
    "/tenants/{tenant_id}/conversations/{conversation_id}/messages",
    response_model=conversation_dto.MessageListResponseDTO,
)
def list_messages_for_tenant(
    tenant_id: str,
    conversation_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> conversation_dto.MessageListResponseDTO:
    return container.conversation_query_service.list_messages(tenant_id, conversation_id)


@router.put(
    "/tenants/{tenant_id}/conversations/{conversation_id}/control-mode",
    response_model=conversation_dto.ConversationControlModeResponseDTO,
)
def update_control_mode_for_tenant(
    tenant_id: str,
    conversation_id: str,
    update_dto: conversation_dto.UpdateConversationControlModeDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> conversation_dto.ConversationControlModeResponseDTO:
    admin_audit.info(
        "admin.conversation.update_control_mode",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "new_mode": update_dto.control_mode,
        },
    )
    return container.conversation_control_service.update_control_mode_for_tenant(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        update_dto=update_dto,
    )


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/messages",
    response_model=conversation_dto.MessageSentResponseDTO,
    status_code=fastapi.status.HTTP_201_CREATED,
)
def send_message_for_tenant(
    tenant_id: str,
    conversation_id: str,
    send_dto: conversation_dto.SendProfessionalMessageDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> conversation_dto.MessageSentResponseDTO:
    admin_audit.info(
        "admin.conversation.send_message",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
        },
    )
    return container.conversation_control_service.send_professional_message_for_tenant(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        send_dto=send_dto,
    )


@router.delete(
    "/tenants/{tenant_id}/conversations/{conversation_id}/messages",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
    dependencies=[fastapi.Depends(http_dependencies.require_dev_endpoints)],
)
def reset_messages_for_tenant(
    tenant_id: str,
    conversation_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> None:
    admin_audit.info(
        "admin.conversation.reset_messages",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
        },
    )
    container.conversation_control_service.reset_messages_for_tenant(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )


# ---------------------------------------------------------------------------
# Manual appointments
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/manual-appointments",
    response_model=manual_appointment_dto.ManualAppointmentListResponseDTO,
)
def list_manual_appointments_for_tenant(
    tenant_id: str,
    status: str | None = None,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> manual_appointment_dto.ManualAppointmentListResponseDTO:
    return container.manual_appointment_service.list_appointments_for_tenant(tenant_id, status)


@router.post(
    "/tenants/{tenant_id}/manual-appointments",
    response_model=manual_appointment_dto.ManualAppointmentDTO,
    status_code=fastapi.status.HTTP_201_CREATED,
)
def create_manual_appointment_for_tenant(
    tenant_id: str,
    create_dto: manual_appointment_dto.CreateManualAppointmentDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> manual_appointment_dto.ManualAppointmentDTO:
    admin_audit.info(
        "admin.manual_appointment.create",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id},
    )
    return container.manual_appointment_service.create_appointment_for_tenant(tenant_id, create_dto)


@router.put(
    "/tenants/{tenant_id}/manual-appointments/{appointment_id}/reschedule",
    response_model=manual_appointment_dto.ManualAppointmentDTO,
)
def reschedule_manual_appointment_for_tenant(
    tenant_id: str,
    appointment_id: str,
    input_dto: manual_appointment_dto.RescheduleManualAppointmentDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> manual_appointment_dto.ManualAppointmentDTO:
    admin_audit.info(
        "admin.manual_appointment.reschedule",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "appointment_id": appointment_id,
        },
    )
    return container.manual_appointment_service.reschedule_appointment_for_tenant(
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        input_dto=input_dto,
    )


@router.delete(
    "/tenants/{tenant_id}/manual-appointments/{appointment_id}",
    response_model=manual_appointment_dto.ManualAppointmentDTO,
)
def cancel_manual_appointment_for_tenant(
    tenant_id: str,
    appointment_id: str,
    input_dto: manual_appointment_dto.CancelManualAppointmentDTO | None = fastapi.Body(
        default=None
    ),
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> manual_appointment_dto.ManualAppointmentDTO:
    admin_audit.info(
        "admin.manual_appointment.cancel",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "appointment_id": appointment_id,
        },
    )
    resolved_input = (
        input_dto
        if input_dto is not None
        else manual_appointment_dto.CancelManualAppointmentDTO(reason=None)
    )
    return container.manual_appointment_service.cancel_appointment_for_tenant(
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        input_dto=resolved_input,
    )


@router.put(
    "/tenants/{tenant_id}/manual-appointments/{appointment_id}/payment",
    response_model=manual_appointment_dto.ManualAppointmentDTO,
)
def update_manual_appointment_payment_for_tenant(
    tenant_id: str,
    appointment_id: str,
    input_dto: manual_appointment_dto.UpdateManualAppointmentPaymentDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> manual_appointment_dto.ManualAppointmentDTO:
    admin_audit.info(
        "admin.manual_appointment.update_payment",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "appointment_id": appointment_id,
        },
    )
    return container.manual_appointment_service.update_payment_for_tenant(
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        input_dto=input_dto,
    )


@router.post(
    "/tenants/{tenant_id}/manual-appointments/{appointment_id}/change-modality",
    response_model=manual_appointment_dto.ManualAppointmentDTO,
)
def change_manual_appointment_modality_for_tenant(
    tenant_id: str,
    appointment_id: str,
    input_dto: manual_appointment_dto.ChangeManualAppointmentModalityInputDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> manual_appointment_dto.ManualAppointmentDTO:
    admin_audit.info(
        "admin.manual_appointment.change_modality",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "appointment_id": appointment_id,
        },
    )
    return container.manual_appointment_service.change_modality_for_tenant(
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        input_dto=input_dto,
    )


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/scheduling-requests",
    response_model=scheduling_dto.SchedulingRequestListResponseDTO,
)
def list_scheduling_requests_for_tenant(
    tenant_id: str,
    status: str | None = None,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.SchedulingRequestListResponseDTO:
    return container.scheduling_inbox_service.list_requests_for_tenant(tenant_id, status=status)


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/consultation-review",
    response_model=scheduling_dto.ConsultationReviewDecisionResponseDTO,
)
def resolve_consultation_review_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    review_dto: scheduling_dto.ConsultationReviewDecisionDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.ConsultationReviewDecisionResponseDTO:
    admin_audit.info(
        "admin.scheduling.consultation_review",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    return container.scheduling_inbox_service.resolve_consultation_review_for_tenant(
        tenant_id=tenant_id,
        actor_user_id=claims.sub,
        conversation_id=conversation_id,
        request_id=request_id,
        input_dto=review_dto,
    )


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/payment-review",
    response_model=scheduling_dto.PaymentReviewDecisionResponseDTO,
)
def resolve_payment_review_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    review_dto: scheduling_dto.PaymentReviewDecisionDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.PaymentReviewDecisionResponseDTO:
    admin_audit.info(
        "admin.scheduling.payment_review",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    return container.scheduling_inbox_service.resolve_payment_review_for_tenant(
        tenant_id=tenant_id,
        actor_user_id=claims.sub,
        conversation_id=conversation_id,
        request_id=request_id,
        input_dto=review_dto,
    )


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/professional-slots",
    response_model=scheduling_dto.ProfessionalSubmitSlotsResponseDTO,
)
def submit_professional_slots_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    submit_dto: scheduling_dto.ProfessionalSubmitSlotsDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.ProfessionalSubmitSlotsResponseDTO:
    admin_audit.info(
        "admin.scheduling.submit_slots",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    return container.scheduling_inbox_service.submit_professional_slots_for_tenant(
        tenant_id=tenant_id,
        actor_user_id=claims.sub,
        conversation_id=conversation_id,
        request_id=request_id,
        submit_dto=submit_dto,
    )


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/reschedule",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def reschedule_booked_slot_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    input_dto: scheduling_dto.RescheduleBookedSlotInputDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    admin_audit.info(
        "admin.scheduling.reschedule_booked_slot",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    return container.scheduling_service.reschedule_booked_slot(
        tenant_id=tenant_id,
        request_id=request_id,
        input_dto=input_dto,
    )


@router.delete(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/booked-slot",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def cancel_booked_slot_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    input_dto: scheduling_dto.CancelBookedSlotInputDTO | None = fastapi.Body(default=None),
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    admin_audit.info(
        "admin.scheduling.cancel_booked_slot",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    resolved_input_dto = (
        input_dto if input_dto is not None else scheduling_dto.CancelBookedSlotInputDTO(reason=None)
    )
    return container.scheduling_service.cancel_booked_slot(
        tenant_id=tenant_id,
        request_id=request_id,
        input_dto=resolved_input_dto,
    )


@router.put(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/booked-payment",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def update_booked_payment_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    input_dto: scheduling_dto.UpdateBookedSlotPaymentInputDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    admin_audit.info(
        "admin.scheduling.update_booked_payment",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    return container.scheduling_service.update_booked_payment(
        tenant_id=tenant_id,
        request_id=request_id,
        input_dto=input_dto,
    )


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/requests/{request_id}/change-modality",
    response_model=scheduling_dto.SchedulingRequestSummaryDTO,
)
def change_booked_slot_modality_for_tenant(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    input_dto: scheduling_dto.ChangeBookedModalityInputDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    admin_audit.info(
        "admin.scheduling.change_booked_modality",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
        },
    )
    return container.scheduling_service.change_booked_modality(
        tenant_id=tenant_id,
        request_id=request_id,
        input_dto=input_dto,
    )


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/scheduling/close-session",
)
def close_scheduling_session_for_tenant(
    tenant_id: str,
    conversation_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> dict[str, str]:
    admin_audit.info(
        "admin.scheduling.close_session",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
        },
    )
    return container.scheduling_service.close_session(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )


@router.get(
    "/tenants/{tenant_id}/scheduling/availability",
    response_model=google_calendar_dto.GoogleCalendarAvailabilityResponseDTO,
)
def get_scheduling_availability_for_tenant(
    tenant_id: str,
    from_at: datetime.datetime = fastapi.Query(alias="from"),
    to_at: datetime.datetime = fastapi.Query(alias="to"),
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> google_calendar_dto.GoogleCalendarAvailabilityResponseDTO:
    return container.google_calendar_onboarding_service.get_availability(
        tenant_id=tenant_id,
        from_at=from_at,
        to_at=to_at,
    )


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/reminders",
    response_model=scheduled_reminder_dto.ScheduledReminderListResponseDTO,
)
def list_reminders_for_tenant(
    tenant_id: str,
    status: str | None = None,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> scheduled_reminder_dto.ScheduledReminderListResponseDTO:
    return container.reminder_service.list_reminders(tenant_id, status)


@router.post("/tenants/{tenant_id}/reminders/{reminder_id}/send-now")
def send_reminder_now_for_tenant(
    tenant_id: str,
    reminder_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> dict[str, str]:
    admin_audit.info(
        "admin.reminder.send_now",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "reminder_id": reminder_id,
        },
    )
    return container.reminder_service.send_reminder_now(
        tenant_id=tenant_id,
        reminder_id=reminder_id,
    )


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/tags",
    response_model=tag_dto.TagListResponseDTO,
)
def list_tags_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> tag_dto.TagListResponseDTO:
    return container.tag_service.list_tags_for_tenant(tenant_id)


@router.post(
    "/tenants/{tenant_id}/tags",
    response_model=tag_dto.TagDTO,
    status_code=fastapi.status.HTTP_201_CREATED,
)
def create_tag_for_tenant(
    tenant_id: str,
    create_dto: tag_dto.CreateTagDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> tag_dto.TagDTO:
    admin_audit.info(
        "admin.tag.create",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id},
    )
    return container.tag_service.create_custom_tag_for_tenant(tenant_id, create_dto)


@router.put(
    "/tenants/{tenant_id}/tags/{tag_id}",
    response_model=tag_dto.TagDTO,
)
def update_tag_for_tenant(
    tenant_id: str,
    tag_id: str,
    update_dto: tag_dto.UpdateTagDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> tag_dto.TagDTO:
    admin_audit.info(
        "admin.tag.update",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id, "tag_id": tag_id},
    )
    return container.tag_service.update_tag_for_tenant(tenant_id, tag_id, update_dto)


@router.delete(
    "/tenants/{tenant_id}/tags/{tag_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def delete_tag_for_tenant(
    tenant_id: str,
    tag_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> None:
    admin_audit.info(
        "admin.tag.delete",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id, "tag_id": tag_id},
    )
    container.tag_service.delete_tag_for_tenant(tenant_id, tag_id)


@router.post(
    "/tenants/{tenant_id}/conversations/{conversation_id}/tags/{tag_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def assign_tag_to_conversation_for_tenant(
    tenant_id: str,
    conversation_id: str,
    tag_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> None:
    admin_audit.info(
        "admin.tag.assign",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "tag_id": tag_id,
        },
    )
    container.tag_service.assign_tag_to_conversation_for_tenant(tenant_id, conversation_id, tag_id)


@router.delete(
    "/tenants/{tenant_id}/conversations/{conversation_id}/tags/{tag_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def remove_tag_from_conversation_for_tenant(
    tenant_id: str,
    conversation_id: str,
    tag_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> None:
    admin_audit.info(
        "admin.tag.remove",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "tag_id": tag_id,
        },
    )
    container.tag_service.remove_tag_from_conversation_for_tenant(
        tenant_id, conversation_id, tag_id
    )


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/blacklist",
    response_model=blacklist_dto.BlacklistListResponseDTO,
)
def list_blacklist_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> blacklist_dto.BlacklistListResponseDTO:
    return container.blacklist_service.list_entries_for_tenant(tenant_id)


@router.post(
    "/tenants/{tenant_id}/blacklist",
    response_model=blacklist_dto.BlacklistEntryDTO,
)
def upsert_blacklist_entry_for_tenant(
    tenant_id: str,
    upsert_dto: blacklist_dto.UpsertBlacklistEntryDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> blacklist_dto.BlacklistEntryDTO:
    admin_audit.info(
        "admin.blacklist.upsert",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "whatsapp_user_id": upsert_dto.whatsapp_user_id,
        },
    )
    return container.blacklist_service.upsert_entry_for_tenant(tenant_id, upsert_dto)


@router.delete(
    "/tenants/{tenant_id}/blacklist/{whatsapp_user_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def delete_blacklist_entry_for_tenant(
    tenant_id: str,
    whatsapp_user_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> None:
    admin_audit.info(
        "admin.blacklist.delete",
        extra={
            "admin_user_id": claims.sub,
            "tenant_id": tenant_id,
            "whatsapp_user_id": whatsapp_user_id,
        },
    )
    container.blacklist_service.delete_entry_for_tenant(tenant_id, whatsapp_user_id)


# ---------------------------------------------------------------------------
# Configuration (agent)
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/agent/system-prompt",
    response_model=agent_dto.SystemPromptResponseDTO,
)
def get_system_prompt_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> agent_dto.SystemPromptResponseDTO:
    return container.agent_service.get_system_prompt(tenant_id)


@router.put(
    "/tenants/{tenant_id}/agent/system-prompt",
    response_model=agent_dto.SystemPromptResponseDTO,
)
def update_system_prompt_for_tenant(
    tenant_id: str,
    update_dto: agent_dto.UpdateSystemPromptDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> agent_dto.SystemPromptResponseDTO:
    admin_audit.info(
        "admin.agent.update_system_prompt",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id},
    )
    return container.agent_service.update_system_prompt(tenant_id, update_dto)


@router.get(
    "/tenants/{tenant_id}/agent/settings",
    response_model=agent_dto.AgentSettingsResponseDTO,
)
def get_agent_settings_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> agent_dto.AgentSettingsResponseDTO:
    return container.agent_service.get_agent_settings(tenant_id)


@router.put(
    "/tenants/{tenant_id}/agent/settings",
    response_model=agent_dto.AgentSettingsResponseDTO,
)
def update_agent_settings_for_tenant(
    tenant_id: str,
    update_dto: agent_dto.UpdateAgentSettingsDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> agent_dto.AgentSettingsResponseDTO:
    admin_audit.info(
        "admin.agent.update_settings",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id},
    )
    return container.agent_service.update_agent_settings(tenant_id, update_dto)


@router.get(
    "/tenants/{tenant_id}/agent/professional-profile",
    response_model=agent_dto.ProfessionalProfileResponseDTO,
)
def get_professional_profile_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> agent_dto.ProfessionalProfileResponseDTO:
    return container.agent_service.get_professional_profile(tenant_id)


@router.put(
    "/tenants/{tenant_id}/agent/professional-profile",
    response_model=agent_dto.ProfessionalProfileResponseDTO,
)
def update_professional_profile_for_tenant(
    tenant_id: str,
    update_dto: agent_dto.UpdateProfessionalProfileDTO,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> agent_dto.ProfessionalProfileResponseDTO:
    admin_audit.info(
        "admin.agent.update_professional_profile",
        extra={"admin_user_id": claims.sub, "tenant_id": tenant_id},
    )
    return container.agent_service.update_professional_profile(tenant_id, update_dto)


# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/google-calendar/connection",
    response_model=google_calendar_dto.GoogleCalendarConnectionStatusDTO,
)
def get_google_calendar_connection_for_tenant(
    tenant_id: str,
    claims: auth_dto.TokenClaimsDTO = _admin_dep,
    container: app_container.AppContainer = _container_dep,
) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
    return container.google_calendar_onboarding_service.get_connection_status(tenant_id)
