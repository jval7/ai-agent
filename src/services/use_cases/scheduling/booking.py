"""Booking sub-domain for scheduling.

What lives here:
  - _book_slot_and_create_event: core booking logic — conflict check,
    calendar event creation, BOOKED transition, auto-close task scheduling,
    and reminder scheduling.
  - confirm_selected_slot_and_create_event_impl: validates the request is in
    AWAITING_PATIENT_CHOICE and delegates to _book_slot_and_create_event.
  - archive_conversation_subsession_after_booking: archives messages into a
    booking subsession.
  - archive_conversation_subsession_manual_close: archives messages via
    manual-close.
  - reschedule_booked_slot_impl: updates the calendar event and reschedules
    reminders.
  - cancel_booked_slot_impl: deletes the calendar event and resets slot state.
  - update_booked_payment_impl: mutates payment fields on a BOOKED request.
  - change_booked_modality_impl: switches PRESENCIAL↔VIRTUAL on a BOOKED
    request, updating the calendar event and rescheduling reminders.

What does NOT live here:
  - Slot selection / proposal logic (slot_proposals.py).
  - Payment approval from the inbox (payment_approval.py).
  - Conversation session / handoff / close_session transitions (transitions.py).
"""

import datetime
import typing

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.task_scheduler_port as task_scheduler_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.reminder_service as reminder_service_module
import src.services.use_cases.scheduling.helpers as scheduling_helpers
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


# ---------------------------------------------------------------------------
# Subsession archiving
# ---------------------------------------------------------------------------


def archive_conversation_subsession_after_booking(
    tenant_id: str,
    conversation_id: str,
    scheduling_request_id: str,
    calendar_event_id: str,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
) -> None:
    conversation = conversation_repository.get_conversation_by_id(
        tenant_id,
        conversation_id,
    )
    if conversation is None:
        raise service_exceptions.EntityNotFoundError("conversation not found")

    active_messages = conversation_repository.list_messages(
        tenant_id,
        conversation_id,
    )
    sorted_active_messages = sorted(active_messages, key=lambda item: item.created_at)
    conversation.archive_current_session(
        scheduling_request_id=scheduling_request_id,
        calendar_event_id=calendar_event_id,
        messages=sorted_active_messages,
        now=now_value,
    )
    conversation_repository.save_conversation(conversation)
    conversation_repository.delete_messages(tenant_id, conversation_id)
    logger.info(
        "scheduling.subsession_archived_after_booking",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.subsession_archived_after_booking",
                message="conversation messages archived into subsession after booking",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "request_id": scheduling_request_id,
                    "calendar_event_id": calendar_event_id,
                    "archived_messages_count": len(sorted_active_messages),
                    "subsessions_count": len(conversation.subsessions),
                },
            )
        },
    )


def archive_conversation_subsession_manual_close(
    tenant_id: str,
    conversation_id: str,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
) -> None:
    conversation = conversation_repository.get_conversation_by_id(
        tenant_id,
        conversation_id,
    )
    if conversation is None:
        raise service_exceptions.EntityNotFoundError("conversation not found")

    active_messages = conversation_repository.list_messages(
        tenant_id,
        conversation_id,
    )
    sorted_active_messages = sorted(active_messages, key=lambda item: item.created_at)
    conversation.archive_manual_close(
        messages=sorted_active_messages,
        now=now_value,
    )
    conversation_repository.save_conversation(conversation)
    conversation_repository.delete_messages(tenant_id, conversation_id)
    logger.info(
        "scheduling.subsession_archived_manual_close",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.subsession_archived_manual_close",
                message="conversation messages archived into subsession via manual close",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "archived_messages_count": len(sorted_active_messages),
                    "subsessions_count": len(conversation.subsessions),
                },
            )
        },
    )


# ---------------------------------------------------------------------------
# Auto-close task scheduling
# ---------------------------------------------------------------------------


def schedule_auto_close_task(
    tenant_id: str,
    scheduling_request_id: str,
    auto_close_delay_seconds: int,
    task_scheduler: task_scheduler_port.TaskSchedulerPort,
) -> None:
    try:
        task_name = task_scheduler.schedule_auto_close(
            tenant_id=tenant_id,
            scheduling_request_id=scheduling_request_id,
            delay_seconds=auto_close_delay_seconds,
        )
        logger.info(
            "scheduling.auto_close_task_enqueued",
            extra={
                "task_name": task_name,
                "scheduling_request_id": scheduling_request_id,
                "delay_seconds": auto_close_delay_seconds,
            },
        )
    except service_exceptions.ExternalProviderError:
        logger.warning(
            "scheduling.auto_close_task_failed",
            extra={"scheduling_request_id": scheduling_request_id},
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Core booking logic
# ---------------------------------------------------------------------------


def book_slot_and_create_event(
    tenant_id: str,
    conversation_id: str,
    request: scheduling_request_entity.SchedulingRequest,
    selected_slot: scheduling_slot_entity.SchedulingSlot,
    event_summary: str,
    attendee_emails: list[str],
    reminder_payment_status: typing.Literal["PAID", "PENDING"],
    now_value: datetime.datetime,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    gcal_onboarding_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    event_description_builder: event_description_builder_mod.EventDescriptionBuilder,
    task_scheduler: task_scheduler_port.TaskSchedulerPort,
    auto_close_delay_seconds: int,
    tag_service: tag_service_module.TagService | None,
    reminder_service: reminder_service_module.ReminderService | None,
    is_eval_tenant: bool,
) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
    """Create a calendar event and transition the request to BOOKED.

    Checks for conflicts first and returns SLOT_CONFLICT if one is found.
    Schedules the auto-close task and the appointment reminder after a
    successful booking.

    When ``is_eval_tenant`` is True the Calendar integration is skipped
    entirely (no conflict check, no event creation).  The request still
    transitions to BOOKED with ``calendar_event_id=None``.
    """
    if not is_eval_tenant:
        has_conflict = gcal_onboarding_service.has_conflict(
            tenant_id=tenant_id,
            start_at=selected_slot.start_at,
            end_at=selected_slot.end_at,
        )
        if has_conflict:
            return _mark_selected_slot_conflict(
                request=request,
                selected_slot=selected_slot,
                now_value=now_value,
                scheduling_repository=scheduling_repository,
                tag_service=tag_service,
            )

    with_meet = request.appointment_modality == "VIRTUAL"
    if request.appointment_modality is None:
        logger.warning(
            "scheduling.confirm_slot.missing_modality",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.confirm_slot.missing_modality",
                    message="appointment_modality is None; defaulting to PRESENCIAL",
                    data={"tenant_id": tenant_id, "request_id": request.id},
                )
            },
        )

    calendar_event_id: str | None = None
    meet_url: str | None = None

    if is_eval_tenant:
        logger.info(
            "scheduling.calendar.skipped_for_eval_tenant",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.calendar.skipped_for_eval_tenant",
                    message="calendar event creation skipped for eval tenant",
                    data={"tenant_id": tenant_id, "request_id": request.id},
                )
            },
        )
    else:
        try:
            normalized_summary = event_summary.strip()
            if not normalized_summary:
                raise service_exceptions.InvalidStateError("event summary cannot be empty")
            event_description_result = event_description_builder.build(
                tenant_id=tenant_id,
                modality=request.appointment_modality,
                payment_status=request.payment_status,
            )
            event_description = event_description_result.description
            event_location = event_description_result.location
            event = gcal_onboarding_service.create_event(
                tenant_id=tenant_id,
                start_at=selected_slot.start_at,
                end_at=selected_slot.end_at,
                summary=normalized_summary,
                attendee_emails=attendee_emails,
                with_meet=with_meet,
                description=event_description,
                location=event_location,
            )
            calendar_event_id = event.event_id
            meet_url = event.meet_url
        except service_exceptions.ExternalProviderError as error:
            if scheduling_helpers.is_google_conflict_error(str(error)):
                return _mark_selected_slot_conflict(
                    request=request,
                    selected_slot=selected_slot,
                    now_value=now_value,
                    scheduling_repository=scheduling_repository,
                    tag_service=tag_service,
                )
            raise

    for slot in request.slots:
        if slot.id == selected_slot.id:
            slot.status = "BOOKED"
        elif slot.status == "PROPOSED":
            slot.status = "REJECTED"

    request.selected_slot_id = selected_slot.id
    request.calendar_event_id = calendar_event_id
    request.set_status("BOOKED", now_value)
    scheduling_repository.save_request(request)

    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )

    schedule_auto_close_task(
        tenant_id=tenant_id,
        scheduling_request_id=request.id,
        auto_close_delay_seconds=auto_close_delay_seconds,
        task_scheduler=task_scheduler,
    )

    if reminder_service is not None and not is_eval_tenant:
        reminder_service.maybe_schedule_reminder(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=request.id,
            patient_whatsapp_user_id=request.whatsapp_user_id,
            patient_name=request.patient_first_name or "Paciente",
            appointment_start_at=selected_slot.start_at,
            payment_status=reminder_payment_status,
            appointment_modality=request.appointment_modality,
            meet_url=meet_url,
        )

    return scheduling_dto.ConfirmSelectedSlotResponseDTO(
        status="BOOKED",
        request_id=request.id,
        selected_slot_id=selected_slot.id,
        calendar_event_id=calendar_event_id,
        remaining_slot_ids=[],
    )


def _mark_selected_slot_conflict(
    request: scheduling_request_entity.SchedulingRequest,
    selected_slot: scheduling_slot_entity.SchedulingSlot,
    now_value: datetime.datetime,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    tag_service: tag_service_module.TagService | None,
) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
    """Mark the slot as UNAVAILABLE and downgrade the request status."""
    for slot in request.slots:
        if slot.id == selected_slot.id:
            slot.status = "UNAVAILABLE"
            break

    if request.selected_slot_id == selected_slot.id:
        request.selected_slot_id = None

    remaining_slot_ids = scheduling_helpers.list_remaining_slot_ids(request)
    if remaining_slot_ids:
        request.set_status("AWAITING_PATIENT_CHOICE", now_value)
    else:
        request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
    scheduling_repository.save_request(request)

    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            new_status=request.status,
        )

    return scheduling_dto.ConfirmSelectedSlotResponseDTO(
        status="SLOT_CONFLICT",
        request_id=request.id,
        selected_slot_id=None,
        calendar_event_id=None,
        remaining_slot_ids=remaining_slot_ids,
    )


# ---------------------------------------------------------------------------
# confirm_selected_slot_and_create_event
# ---------------------------------------------------------------------------


def confirm_selected_slot_and_create_event_impl(
    tenant_id: str,
    conversation_id: str,
    input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    gcal_onboarding_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    event_description_builder: event_description_builder_mod.EventDescriptionBuilder,
    task_scheduler: task_scheduler_port.TaskSchedulerPort,
    auto_close_delay_seconds: int,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
    reminder_service: reminder_service_module.ReminderService | None,
    is_eval_tenant: bool,
) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
    request = scheduling_repository.get_request_by_id(tenant_id, input_dto.request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if request.conversation_id != conversation_id:
        raise service_exceptions.AuthorizationError(
            "scheduling request does not belong to conversation"
        )
    if request.status != "AWAITING_PATIENT_CHOICE":
        raise service_exceptions.InvalidStateError(
            "scheduling request is not waiting for patient choice"
        )

    selected_slot = scheduling_helpers.find_selectable_slot(request, input_dto.slot_id)
    if selected_slot is None:
        raise service_exceptions.InvalidStateError("selected slot is not available")

    # Persist the resolved patient name on the request so reminder
    # messages and the admin reminders list show the actual name instead
    # of the "Paciente" fallback.
    if input_dto.patient_first_name is not None:
        request.patient_first_name = input_dto.patient_first_name
    if input_dto.patient_last_name is not None:
        request.patient_last_name = input_dto.patient_last_name

    now_value = clock.now()

    return book_slot_and_create_event(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        request=request,
        selected_slot=selected_slot,
        event_summary=input_dto.event_summary,
        attendee_emails=input_dto.attendee_emails,
        reminder_payment_status="PAID",
        now_value=now_value,
        scheduling_repository=scheduling_repository,
        gcal_onboarding_service=gcal_onboarding_service,
        event_description_builder=event_description_builder,
        task_scheduler=task_scheduler,
        auto_close_delay_seconds=auto_close_delay_seconds,
        tag_service=tag_service,
        reminder_service=reminder_service,
        is_eval_tenant=is_eval_tenant,
    )


# ---------------------------------------------------------------------------
# Reschedule, cancel, update payment, change modality
# ---------------------------------------------------------------------------


def reschedule_booked_slot_impl(
    tenant_id: str,
    request_id: str,
    input_dto: scheduling_dto.RescheduleBookedSlotInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    gcal_onboarding_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    clock: clock_port.ClockPort,
    patient_repository: patient_repository_port.PatientRepositoryPort | None,
    reminder_service: reminder_service_module.ReminderService | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if request.calendar_event_id is None:
        raise service_exceptions.InvalidStateError(
            "booked scheduling request has no calendar event"
        )

    booked_slot = scheduling_helpers.find_booked_slot(request)
    if booked_slot is None:
        raise service_exceptions.InvalidStateError("booked scheduling request has no booked slot")

    event_summary = scheduling_helpers.resolve_booked_event_summary(
        request=request,
        requested_summary=input_dto.event_summary,
    )
    reschedule_attendee_emails: list[str] = []
    if patient_repository is not None:
        reschedule_patient = patient_repository.get_by_whatsapp_user(
            tenant_id, request.whatsapp_user_id
        )
        if reschedule_patient is not None:
            reschedule_attendee_emails = [reschedule_patient.email]
    updated_event = gcal_onboarding_service.update_event(
        tenant_id=tenant_id,
        event_id=request.calendar_event_id,
        start_at=input_dto.start_at,
        end_at=input_dto.end_at,
        timezone=input_dto.timezone,
        summary=event_summary,
        attendee_emails=reschedule_attendee_emails,
    )

    if reminder_service is not None:
        reminder_service.cancel_reminders_for_source(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=request.id,
        )
    booked_slot.start_at = updated_event.start_at
    booked_slot.end_at = updated_event.end_at
    booked_slot.timezone = input_dto.timezone
    now_value = clock.now()
    request.updated_at = now_value
    scheduling_repository.save_request(request)
    if reminder_service is not None:
        reminder_service.maybe_schedule_reminder(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=request.id,
            patient_whatsapp_user_id=request.whatsapp_user_id,
            patient_name=request.patient_first_name or "Paciente",
            appointment_start_at=input_dto.start_at,
            payment_status="PAID",
            appointment_modality=request.appointment_modality,
            meet_url=updated_event.meet_url,
        )
    logger.info(
        "scheduling.booked_slot_rescheduled",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.booked_slot_rescheduled",
                message="booked scheduling request rescheduled",
                data={
                    "tenant_id": tenant_id,
                    "request_id": request.id,
                    "calendar_event_id": request.calendar_event_id,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(request)


def cancel_booked_slot_impl(
    tenant_id: str,
    request_id: str,
    input_dto: scheduling_dto.CancelBookedSlotInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    gcal_onboarding_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    clock: clock_port.ClockPort,
    reminder_service: reminder_service_module.ReminderService | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")

    calendar_event_id = request.calendar_event_id
    if calendar_event_id is not None:
        try:
            gcal_onboarding_service.delete_event(
                tenant_id=tenant_id,
                event_id=calendar_event_id,
            )
        except service_exceptions.ExternalProviderError as error:
            if not scheduling_helpers.is_google_not_found_error(str(error)):
                raise

    now_value = clock.now()
    for slot in request.slots:
        if slot.status in ("BOOKED", "SELECTED"):
            slot.status = "REJECTED"
    request.calendar_event_id = None
    request.selected_slot_id = None
    normalized_reason = scheduling_helpers.normalize_patient_text(input_dto.reason)
    if normalized_reason is not None:
        request.professional_note = normalized_reason
    if reminder_service is not None:
        reminder_service.cancel_reminders_for_source(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=request.id,
        )
    request.updated_at = now_value
    scheduling_repository.save_request(request)
    logger.info(
        "scheduling.booked_slot_cancelled",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.booked_slot_cancelled",
                message="booked scheduling request cancelled from agenda",
                data={
                    "tenant_id": tenant_id,
                    "request_id": request.id,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(request)


def update_booked_payment_impl(
    tenant_id: str,
    request_id: str,
    input_dto: scheduling_dto.UpdateBookedSlotPaymentInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    clock: clock_port.ClockPort,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    now_value = clock.now()
    request.payment_amount_cop = input_dto.payment_amount_cop
    request.payment_currency = input_dto.payment_currency
    request.payment_method = input_dto.payment_method
    request.payment_status = input_dto.payment_status
    request.payment_updated_at = now_value
    request.updated_at = now_value
    scheduling_repository.save_request(request)
    logger.info(
        "scheduling.booked_payment_updated",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.booked_payment_updated",
                message="booked scheduling request payment updated",
                data={
                    "tenant_id": tenant_id,
                    "request_id": request.id,
                    "payment_status": request.payment_status,
                    "payment_method": request.payment_method,
                    "payment_amount_cop": request.payment_amount_cop,
                    "payment_currency": request.payment_currency,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(request)


def change_booked_modality_impl(
    tenant_id: str,
    request_id: str,
    input_dto: scheduling_dto.ChangeBookedModalityInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    gcal_onboarding_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    event_description_builder: event_description_builder_mod.EventDescriptionBuilder,
    clock: clock_port.ClockPort,
    patient_repository: patient_repository_port.PatientRepositoryPort | None,
    reminder_service: reminder_service_module.ReminderService | None,
    is_eval_tenant: bool,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if request.status != "BOOKED":
        raise service_exceptions.InvalidStateError("only BOOKED requests can change modality")

    booked_slot = scheduling_helpers.find_booked_slot(request)
    if booked_slot is None:
        raise service_exceptions.InvalidStateError("no booked slot found in request")

    now_value = clock.now()
    if booked_slot.start_at <= now_value:
        raise service_exceptions.InvalidStateError("cannot change modality for past appointments")

    # Idempotency: same modality → noop
    if request.appointment_modality == input_dto.new_modality:
        return scheduling_helpers.to_summary_dto(request)

    new_modality = input_dto.new_modality
    with_meet = new_modality == "VIRTUAL"

    new_meet_url: str | None = None
    if not is_eval_tenant and request.calendar_event_id is not None:
        attendee_emails: list[str] = []
        if patient_repository is not None:
            patient = patient_repository.get_by_whatsapp_user(tenant_id, request.whatsapp_user_id)
            if patient is not None:
                attendee_emails = [patient.email]

        event_description_result = event_description_builder.build(
            tenant_id=tenant_id,
            modality=new_modality,
            payment_status=request.payment_status,
        )
        event_summary = scheduling_helpers.resolve_booked_event_summary(
            request=request,
            requested_summary=None,
        )
        updated_event = gcal_onboarding_service.update_event(
            tenant_id=tenant_id,
            event_id=request.calendar_event_id,
            start_at=booked_slot.start_at,
            end_at=booked_slot.end_at,
            timezone=booked_slot.timezone,
            summary=event_summary,
            attendee_emails=attendee_emails,
            description=event_description_result.description,
            location=event_description_result.location,
            with_meet=with_meet,
        )
        new_meet_url = updated_event.meet_url

    request.appointment_modality = new_modality
    request.updated_at = now_value
    scheduling_repository.save_request(request)

    if reminder_service is not None and not is_eval_tenant:
        reminder_service.cancel_reminders_for_source(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=request.id,
        )
        reminder_payment_status: typing.Literal["PAID", "PENDING"] = (
            "PAID" if request.payment_status == "PAID" else "PENDING"
        )
        reminder_service.maybe_schedule_reminder(
            tenant_id=tenant_id,
            source_type="SCHEDULING_REQUEST",
            source_id=request.id,
            patient_whatsapp_user_id=request.whatsapp_user_id,
            patient_name=request.patient_first_name or "Paciente",
            appointment_start_at=booked_slot.start_at,
            payment_status=reminder_payment_status,
            appointment_modality=new_modality,
            meet_url=new_meet_url,
        )

    logger.info(
        "scheduling.modality_changed",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.modality_changed",
                message="booked appointment modality changed",
                data={
                    "tenant_id": tenant_id,
                    "request_id": request.id,
                    "new_modality": new_modality,
                    "calendar_event_id": request.calendar_event_id,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(request)
