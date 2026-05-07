"""Reschedule sub-domain for scheduling.

What lives here:
  - submit_reschedule_for_review_impl: patient requests to reschedule.
    Two valid entry points are supported:
      (a) BOOKED SR — the patient comes back later (NO_ACTIVE_REQUEST flow).
      (b) AWAITING_ATTENDANCE_CONFIRMATION + RETRY placeholder — the
          reminder pre-positioned a synthetic SR; the real appointment lives
          in source_appointment_id (either a SR or a manual_appt).
    Creates a child RESCHEDULE SR that goes through the normal review flow.
  - confirm_rescheduled_slot_impl: confirms the slot selected for the
    RESCHEDULE SR, moves the Google Calendar event in place, promotes
    the child to BOOKED (new active booking), detaches the calendar event
    from the source, and closes any other open SRs in the conversation.

What does NOT live here:
  - Calendar event creation for initial bookings (booking.py).
  - Slot proposal / selection for initial bookings (slot_proposals.py).
  - Payment approval (payment_approval.py).
  - Session archiving or lifecycle (transitions.py).
"""

import typing

import pydantic

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.reminder_service as reminder_service_module
import src.services.use_cases.scheduling.helpers as scheduling_helpers
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


class _RescheduleSourceData(pydantic.BaseModel):
    """Data inherited by a RESCHEDULE child SR from its booking source.

    The source can be either an existing BOOKED SR or a manual_appointment
    referenced by a reminder-pre-positioned placeholder SR.  This struct
    normalises both cases so the child SR can be built uniformly.
    """

    whatsapp_user_id: str
    consultation_reason: str | None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None
    patient_location: str | None
    patient_first_name: str | None
    patient_last_name: str | None
    patient_age: int | None
    source_appointment_id: str
    source_appointment_kind: typing.Literal["SCHEDULING_REQUEST", "MANUAL_APPOINTMENT"]


def _resolve_reschedule_source_data(
    tenant_id: str,
    original_request: scheduling_request_entity.SchedulingRequest,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    manual_appointment_repository: (
        manual_appointment_repository_port.ManualAppointmentRepositoryPort | None
    ),
    patient_repository: patient_repository_port.PatientRepositoryPort | None,
) -> _RescheduleSourceData:
    """Derive the source data for the RESCHEDULE child SR.

    Supports both a BOOKED SR (direct path) and a reminder-pre-positioned
    AWAITING_ATTENDANCE_CONFIRMATION + RETRY placeholder that points to the
    real booking via source_appointment_id.
    """
    if original_request.status == "BOOKED":
        return _RescheduleSourceData(
            whatsapp_user_id=original_request.whatsapp_user_id,
            consultation_reason=original_request.consultation_reason,
            appointment_modality=original_request.appointment_modality,
            patient_location=original_request.patient_location,
            patient_first_name=original_request.patient_first_name,
            patient_last_name=original_request.patient_last_name,
            patient_age=original_request.patient_age,
            source_appointment_id=original_request.id,
            source_appointment_kind="SCHEDULING_REQUEST",
        )

    # Reminder pre-position placeholder: real booking lives in source_*.
    is_placeholder = (
        original_request.status == "AWAITING_ATTENDANCE_CONFIRMATION"
        and original_request.request_kind == "RETRY"
        and original_request.source_appointment_id is not None
    )
    if not is_placeholder:
        raise service_exceptions.InvalidStateError(
            "solo se puede reagendar una cita en estado BOOKED"
        )

    source_id = original_request.source_appointment_id
    source_kind = original_request.source_appointment_kind
    assert source_id is not None  # checked by is_placeholder

    if source_kind == "SCHEDULING_REQUEST":
        real_source = scheduling_repository.get_request_by_id(tenant_id, source_id)
        if real_source is None:
            raise service_exceptions.EntityNotFoundError("source scheduling request not found")
        return _RescheduleSourceData(
            whatsapp_user_id=real_source.whatsapp_user_id,
            consultation_reason=real_source.consultation_reason,
            appointment_modality=real_source.appointment_modality,
            patient_location=real_source.patient_location,
            patient_first_name=real_source.patient_first_name,
            patient_last_name=real_source.patient_last_name,
            patient_age=real_source.patient_age,
            source_appointment_id=source_id,
            source_appointment_kind="SCHEDULING_REQUEST",
        )

    if source_kind == "MANUAL_APPOINTMENT":
        if manual_appointment_repository is None:
            raise service_exceptions.InvalidStateError(
                "manual appointment repository not configured"
            )
        manual = manual_appointment_repository.get_by_id(tenant_id, source_id)
        if manual is None:
            raise service_exceptions.EntityNotFoundError("source manual appointment not found")
        patient = (
            patient_repository.get_by_whatsapp_user(tenant_id, manual.patient_whatsapp_user_id)
            if patient_repository is not None
            else None
        )
        inferred_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] = (
            "VIRTUAL" if manual.is_virtual else "PRESENCIAL"
        )
        return _RescheduleSourceData(
            whatsapp_user_id=manual.patient_whatsapp_user_id,
            consultation_reason=manual.summary,
            appointment_modality=inferred_modality,
            patient_location=patient.location if patient is not None else None,
            patient_first_name=patient.first_name if patient is not None else None,
            patient_last_name=patient.last_name if patient is not None else None,
            patient_age=patient.age if patient is not None else None,
            source_appointment_id=source_id,
            source_appointment_kind="MANUAL_APPOINTMENT",
        )

    raise service_exceptions.InvalidStateError("unknown source appointment kind for reschedule")


def submit_reschedule_for_review_impl(
    tenant_id: str,
    conversation_id: str,
    whatsapp_user_id: str,
    input_dto: scheduling_dto.SubmitRescheduleForReviewToolInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    id_generator: id_generator_port.IdGeneratorPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
    manual_appointment_repository: (
        manual_appointment_repository_port.ManualAppointmentRepositoryPort | None
    ),
    patient_repository: patient_repository_port.PatientRepositoryPort | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Create a RESCHEDULE child SR for a patient requesting to reschedule."""
    # 1. Load and validate the original SR.
    original_request = scheduling_repository.get_request_by_id(
        tenant_id, input_dto.original_request_id
    )
    if original_request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if original_request.tenant_id != tenant_id:
        raise service_exceptions.AuthorizationError("scheduling request does not belong to tenant")

    # 2. Resolve the data source for the RESCHEDULE child.
    source_data = _resolve_reschedule_source_data(
        tenant_id=tenant_id,
        original_request=original_request,
        scheduling_repository=scheduling_repository,
        manual_appointment_repository=manual_appointment_repository,
        patient_repository=patient_repository,
    )

    # 3. Verify no active reschedule SR already exists for the resolved source.
    existing_requests = scheduling_repository.list_requests_by_conversation(
        tenant_id,
        conversation_id,
    )
    for req in existing_requests:
        if (
            req.request_kind == "RESCHEDULE"
            and req.source_appointment_id == source_data.source_appointment_id
            and req.status
            not in (
                "SESSION_CLOSED",
                "CANCELLED",
                "CONSULTATION_REJECTED",
                "HUMAN_HANDOFF",
            )
        ):
            raise service_exceptions.InvalidStateError(
                "ya hay un reagendamiento en curso para esta cita"
            )

    # 4. Create the child RESCHEDULE SR inheriting data from source.
    now_value = clock.now()
    open_requests = scheduling_repository.list_requests_by_conversation(
        tenant_id,
        conversation_id,
    )
    new_request = scheduling_request_entity.SchedulingRequest(
        id=id_generator.new_id(),
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        whatsapp_user_id=source_data.whatsapp_user_id,
        request_kind="RESCHEDULE",
        status="AWAITING_CONSULTATION_REVIEW",
        round_number=len(open_requests) + 1,
        patient_preference_note=input_dto.reason,
        rejection_summary=None,
        professional_note=None,
        consultation_reason=source_data.consultation_reason,
        appointment_modality=source_data.appointment_modality,
        patient_location=source_data.patient_location,
        patient_first_name=source_data.patient_first_name,
        patient_last_name=source_data.patient_last_name,
        patient_age=source_data.patient_age,
        slots=[],
        slot_options_map={},
        selected_slot_id=None,
        calendar_event_id=None,
        source_appointment_id=source_data.source_appointment_id,
        source_appointment_kind=source_data.source_appointment_kind,
        payment_status="PAID",
        created_at=now_value,
        updated_at=now_value,
    )

    # 5. Persist.
    scheduling_repository.save_request(new_request)

    # 6. Sync tags.
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=new_request.status,
        )

    logger.info(
        "scheduling.reschedule_for_review_submitted",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.reschedule_for_review_submitted",
                message="reschedule request created for professional review",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "new_request_id": new_request.id,
                    "original_request_id": input_dto.original_request_id,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(new_request)


def confirm_rescheduled_slot_impl(
    tenant_id: str,
    conversation_id: str,
    input_dto: scheduling_dto.ConfirmRescheduledSlotInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    gcal_onboarding_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    clock: clock_port.ClockPort,
    patient_repository: patient_repository_port.PatientRepositoryPort | None,
    manual_appointment_repository: (
        manual_appointment_repository_port.ManualAppointmentRepositoryPort | None
    ),
    reminder_service: reminder_service_module.ReminderService | None,
    tag_service: tag_service_module.TagService | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Confirm the selected slot for a RESCHEDULE SR.

    Reworked so the post-reschedule conversation state matches a normal booking
    (POST_BOOKING_FOLLOWUP) rather than leaving dangling open SRs that confuse
    the runtime context resolver.

    - Move the Google Calendar event in place (same event_id, new times).
    - Promote the RESCHEDULE child to BOOKED, transferring calendar_event_id
      ownership and marking its slot BOOKED — this is the new active booking.
    - Detach the calendar_event_id from the source SR (and CANCEL the source
      manual_appointment) so the agenda calendar does not render duplicates.
    - Cancel reminders bound to the old source + schedule fresh reminder
      pointing at the promoted child SR.
    - Close any other open SRs in this conversation (e.g. reminder placeholder).
    """
    # 1. Load and validate the RESCHEDULE SR.
    reschedule_request = scheduling_repository.get_request_by_id(tenant_id, input_dto.request_id)
    if reschedule_request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if reschedule_request.request_kind != "RESCHEDULE":
        raise service_exceptions.InvalidStateError("scheduling request is not a reschedule request")
    if reschedule_request.status != "AWAITING_PATIENT_CHOICE":
        raise service_exceptions.InvalidStateError(
            "scheduling request is not waiting for patient choice"
        )
    if reschedule_request.selected_slot_id is None:
        raise service_exceptions.InvalidStateError(
            "no slot selected yet; call select_proposed_slot first"
        )

    # 2. Find the selected slot in the RESCHEDULE SR.
    selected_slot: scheduling_slot_entity.SchedulingSlot | None = None
    for slot in reschedule_request.slots:
        if slot.id == reschedule_request.selected_slot_id:
            selected_slot = slot
            break
    if selected_slot is None:
        raise service_exceptions.InvalidStateError("selected slot not found in reschedule request")

    # 3. Get the source appointment id + kind.
    source_id = reschedule_request.source_appointment_id
    source_kind = reschedule_request.source_appointment_kind
    if source_id is None or source_kind is None:
        raise service_exceptions.InvalidStateError(
            "reschedule request has no source appointment reference"
        )

    # 4. Resolve the source's calendar_event_id (we keep the same Google
    #    Calendar event; only its time changes).
    calendar_event_id: str | None = None
    source_request: scheduling_request_entity.SchedulingRequest | None = None
    manual_appt = None
    if source_kind == "SCHEDULING_REQUEST":
        source_request = scheduling_repository.get_request_by_id(tenant_id, source_id)
        if source_request is None:
            raise service_exceptions.EntityNotFoundError("source scheduling request not found")
        calendar_event_id = source_request.calendar_event_id
    elif source_kind == "MANUAL_APPOINTMENT":
        if manual_appointment_repository is None:
            raise service_exceptions.InvalidStateError(
                "manual appointment repository not configured"
            )
        manual_appt = manual_appointment_repository.get_by_id(tenant_id, source_id)
        if manual_appt is None:
            raise service_exceptions.EntityNotFoundError("source manual appointment not found")
        calendar_event_id = manual_appt.calendar_event_id
    if calendar_event_id is None:
        raise service_exceptions.InvalidStateError(
            "source appointment has no calendar event to reschedule"
        )

    # 5. Update the Google Calendar event in place.
    attendee_emails: list[str] = []
    if patient_repository is not None:
        patient = patient_repository.get_by_whatsapp_user(
            tenant_id, reschedule_request.whatsapp_user_id
        )
        if patient is not None:
            attendee_emails = [patient.email]
    event_summary = scheduling_helpers.resolve_booked_event_summary(
        request=reschedule_request,
        requested_summary=None,
    )
    gcal_onboarding_service.update_event(
        tenant_id=tenant_id,
        event_id=calendar_event_id,
        start_at=selected_slot.start_at,
        end_at=selected_slot.end_at,
        timezone=selected_slot.timezone,
        summary=event_summary,
        attendee_emails=attendee_emails,
    )

    now_value = clock.now()

    # 6. Cancel reminders bound to the old source — the new reminder will
    #    point at the RESCHEDULE child (now the active booking).
    if reminder_service is not None:
        reminder_service.cancel_reminders_for_source(
            tenant_id=tenant_id,
            source_type=source_kind,
            source_id=source_id,
        )

    # 7. Detach the calendar event from the old source so the agenda does
    #    not render it as a duplicate appointment.
    if source_request is not None:
        source_request.calendar_event_id = None
        if source_request.status == "BOOKED":
            source_request.set_status("SESSION_CLOSED", now_value)
        else:
            source_request.updated_at = now_value
        scheduling_repository.save_request(source_request)
    if manual_appt is not None and manual_appointment_repository is not None:
        manual_appt.status = "CANCELLED"
        manual_appt.cancelled_at = now_value
        manual_appt.updated_at = now_value
        manual_appointment_repository.save(manual_appt)

    # 8. Promote the RESCHEDULE child to BOOKED. It now owns the calendar
    #    event and is the active appointment for this conversation, so the
    #    resolver will treat the conversation as POST_BOOKING_FOLLOWUP.
    for slot in reschedule_request.slots:
        if slot.id == reschedule_request.selected_slot_id:
            slot.status = "BOOKED"
            slot.start_at = selected_slot.start_at
            slot.end_at = selected_slot.end_at
            break
    reschedule_request.calendar_event_id = calendar_event_id
    reschedule_request.set_status("BOOKED", now_value)
    scheduling_repository.save_request(reschedule_request)

    # 9. Schedule the next reminder pointing at the new BOOKED SR.
    if reminder_service is not None:
        reminder_service.maybe_schedule_reminder(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=reschedule_request.id,
            patient_whatsapp_user_id=reschedule_request.whatsapp_user_id,
            patient_name=reschedule_request.patient_first_name or "Paciente",
            appointment_start_at=selected_slot.start_at,
            payment_status="PAID",
            appointment_modality=reschedule_request.appointment_modality,
        )

    # 10. Close any other open SRs in this conversation (notably the
    #     reminder pre-position placeholder, which may still be in
    #     AWAITING_ATTENDANCE_CONFIRMATION otherwise).
    open_statuses = {
        "AWAITING_CONSULTATION_REVIEW",
        "AWAITING_CONSULTATION_DETAILS",
        "AWAITING_PATIENT_CHOICE",
        "AWAITING_PAYMENT_CONFIRMATION",
        "AWAITING_ATTENDANCE_CONFIRMATION",
    }
    all_requests = scheduling_repository.list_requests_by_conversation(tenant_id, conversation_id)
    for other_request in all_requests:
        if other_request.id == reschedule_request.id:
            continue
        if other_request.status in open_statuses:
            other_request.set_status("SESSION_CLOSED", now_value)
            scheduling_repository.save_request(other_request)

    # 11. Sync tags to BOOKED.
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="BOOKED",
        )

    logger.info(
        "scheduling.rescheduled_slot_confirmed",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.rescheduled_slot_confirmed",
                message="rescheduled slot confirmed; child promoted to BOOKED",
                data={
                    "tenant_id": tenant_id,
                    "reschedule_request_id": reschedule_request.id,
                    "source_appointment_id": source_id,
                    "source_appointment_kind": source_kind,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(reschedule_request)
