"""Payment-approval sub-domain for scheduling.

What lives here:
  - approve_payment_impl: handles professional approval of a payment review.
    Two branches:
      (a) Original scheduling flow — transitions the request to
          AWAITING_PATIENT_CHOICE after marking payment as PAID.
      (b) Reminder-reply flow — the synthetic request (pre-positioned by
          ReminderService) already has source_appointment_id set; this branch
          marks the source appointment as PAID, closes the synthetic request,
          and sends a WhatsApp confirmation to the patient.
  - _approve_payment_from_reminder: internal helper for branch (b).

Cross-module dependency: calls
  booking.archive_conversation_subsession_manual_close when no WhatsApp
  wiring is available (avoids duplicate archive logic).

What does NOT live here:
  - Calendar event creation or reschedule (booking.py).
  - Session transitions unrelated to payment (transitions.py).
"""

import datetime

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.payment_confirmation_dispatcher as payment_confirmation_dispatcher
import src.services.use_cases.scheduling.booking as scheduling_booking
import src.services.use_cases.scheduling.helpers as scheduling_helpers
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


def _approve_payment_from_reminder(
    request: scheduling_request_entity.SchedulingRequest,
    input_dto: scheduling_dto.PaymentReviewDecisionDTO,
    now_value: datetime.datetime,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    manual_appointment_repository: (
        manual_appointment_repository_port.ManualAppointmentRepositoryPort | None
    ),
    whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort | None,
    whatsapp_connection_repository: (
        whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort | None
    ),
    id_generator: id_generator_port.IdGeneratorPort,
    clock: clock_port.ClockPort,
) -> None:
    """Handle payment approval for a synthetic reminder-reply SchedulingRequest.

    Marks the source appointment as PAID, closes the synthetic request, and
    sends a freeform confirmation message to the patient via WhatsApp.
    All operations are best-effort after the first: failures are logged but
    do not bubble up to the caller — the payment approval must not fail just
    because a side-effect went wrong.
    """
    source_id = request.source_appointment_id
    source_kind = request.source_appointment_kind
    tenant_id = request.tenant_id

    # 1. Update payment_status on the source appointment.
    if source_kind == "MANUAL_APPOINTMENT":
        if manual_appointment_repository is not None:
            source_appt = manual_appointment_repository.get_by_id(tenant_id, source_id or "")
            if source_appt is None:
                logger.warning(
                    "scheduling.approve_reminder_payment.source_not_found",
                    extra={
                        "tenant_id": tenant_id,
                        "source_kind": source_kind,
                        "source_id": source_id,
                    },
                )
            else:
                source_appt.payment_status = "PAID"
                source_appt.payment_amount_cop = input_dto.payment_amount_cop
                source_appt.payment_currency = input_dto.payment_currency
                source_appt.payment_updated_at = now_value
                source_appt.updated_at = now_value
                manual_appointment_repository.save(source_appt)
    elif source_kind == "SCHEDULING_REQUEST":
        source_req = scheduling_repository.get_request_by_id(tenant_id, source_id or "")
        if source_req is None:
            logger.warning(
                "scheduling.approve_reminder_payment.source_not_found",
                extra={
                    "tenant_id": tenant_id,
                    "source_kind": source_kind,
                    "source_id": source_id,
                },
            )
        else:
            source_req.payment_status = "PAID"
            source_req.payment_amount_cop = input_dto.payment_amount_cop
            source_req.payment_currency = input_dto.payment_currency
            source_req.payment_updated_at = now_value
            source_req.updated_at = now_value
            scheduling_repository.save_request(source_req)

    # 2. Close the synthetic request.
    request.set_status("SESSION_CLOSED", now_value)

    # 3. Send freeform confirmation + archive subsession (if chat is open
    # within Meta's 24h window). The dispatcher itself handles the
    # archive_manual_close + delete_messages so we don't need to call
    # archive_conversation_subsession_manual_close beforehand.
    if whatsapp_provider is not None and whatsapp_connection_repository is not None:
        payment_confirmation_dispatcher.confirm_payment_in_chat_if_open(
            tenant_id=tenant_id,
            whatsapp_user_id=request.whatsapp_user_id,
            patient_first_name=request.patient_first_name,
            source_appointment_id=request.source_appointment_id,
            now_value=now_value,
            conversation_repository=conversation_repository,
            whatsapp_connection_repository=whatsapp_connection_repository,
            whatsapp_provider=whatsapp_provider,
            id_generator=id_generator,
            clock=clock,
            scheduling_repository=scheduling_repository,
        )
    else:
        # No whatsapp wiring: still archive subsession so the synthetic
        # request leaves the active list.
        scheduling_booking.archive_conversation_subsession_manual_close(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            now_value=now_value,
            conversation_repository=conversation_repository,
        )

    logger.info(
        "scheduling.approve_reminder_payment.done",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.approve_reminder_payment.done",
                message="reminder payment approved: source marked PAID, session closed",
                data={
                    "tenant_id": tenant_id,
                    "synthetic_request_id": request.id,
                    "source_kind": source_kind,
                    "source_id": source_id,
                },
            )
        },
    )


def approve_payment_impl(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    input_dto: scheduling_dto.PaymentReviewDecisionDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    clock: clock_port.ClockPort,
    id_generator: id_generator_port.IdGeneratorPort,
    tag_service: tag_service_module.TagService | None,
    manual_appointment_repository: (
        manual_appointment_repository_port.ManualAppointmentRepositoryPort | None
    ),
    whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort | None,
    whatsapp_connection_repository: (
        whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort | None
    ),
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Apply the professional's payment decision to an AWAITING_PAYMENT_CONFIRMATION request."""
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if request.conversation_id != conversation_id:
        raise service_exceptions.AuthorizationError(
            "scheduling request does not belong to conversation"
        )
    if request.status != "AWAITING_PAYMENT_CONFIRMATION":
        raise service_exceptions.InvalidStateError(
            "scheduling request is not awaiting payment confirmation"
        )

    now_value = clock.now()
    if input_dto.decision == "APPROVE":
        if (
            request.source_appointment_id is not None
            and request.source_appointment_kind is not None
        ):
            # Reminder-reply flow: the appointment already exists and is BOOKED.
            # Mark the source as PAID, close this synthetic request, and notify patient.
            _approve_payment_from_reminder(
                request=request,
                input_dto=input_dto,
                now_value=now_value,
                scheduling_repository=scheduling_repository,
                conversation_repository=conversation_repository,
                manual_appointment_repository=manual_appointment_repository,
                whatsapp_provider=whatsapp_provider,
                whatsapp_connection_repository=whatsapp_connection_repository,
                id_generator=id_generator,
                clock=clock,
            )
        else:
            # Original scheduling flow: transition to slot selection.
            request.payment_status = "PAID"
            request.payment_amount_cop = input_dto.payment_amount_cop
            request.payment_currency = input_dto.payment_currency
            request.payment_updated_at = now_value
            request.set_status("AWAITING_PATIENT_CHOICE", now_value)

    if input_dto.professional_note is not None:
        request.professional_note = input_dto.professional_note

    request.updated_at = now_value
    scheduling_repository.save_request(request)
    if input_dto.decision == "APPROVE" and tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
    logger.info(
        "scheduling.payment_review_resolved",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.payment_review_resolved",
                message="professional resolved payment review",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "request_id": request.id,
                    "decision": input_dto.decision,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(request)
