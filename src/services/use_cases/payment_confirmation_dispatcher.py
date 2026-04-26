"""Close any open chat session tied to a payment, optionally notifying the
patient via WhatsApp.

Used by both payment-approval paths (manual appointment Pago tab and
post-reminder Conversaciones approval) so they share the same UX:

  * If the patient has a recent INBOUND (within Meta's 24h freeform
    window), send a "pago confirmado" message before closing — Meta only
    accepts freeform inside the window.
  * Always close the session: archive the active conversation subsession
    and cancel any synthetic SchedulingRequest tied to this source so the
    conversation moves out of Pago pendiente / En curso.

Outside the 24h window (or if the patient never chatted) the reminder
template swap PAYMENT->ATTENDANCE keeps the patient informed when the
next reminder fires — that's why we don't try to send anything here.
"""

import datetime
import typing

import src.domain.entities.message as message_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)

_FREEFORM_WINDOW = datetime.timedelta(hours=24)
_OPEN_SCHEDULING_STATUSES = frozenset(
    {
        "AWAITING_CONSULTATION_REVIEW",
        "AWAITING_CONSULTATION_DETAILS",
        "AWAITING_PATIENT_CHOICE",
        "AWAITING_PAYMENT_CONFIRMATION",
        "AWAITING_ATTENDANCE_CONFIRMATION",
        "BOOKED",
    }
)


def _has_recent_inbound(
    conversation_id: str,
    tenant_id: str,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
) -> bool:
    """Return True if any INBOUND message in the conversation is within the
    24h window — Meta's hard limit for freeform replies."""
    messages = conversation_repository.list_messages(tenant_id, conversation_id)
    cutoff = now_value - _FREEFORM_WINDOW
    for message in messages:
        if message.direction == "INBOUND" and message.created_at >= cutoff:
            return True
    return False


def _close_synthetic_request(
    *,
    tenant_id: str,
    conversation_id: str,
    source_appointment_id: str | None,
    now_value: datetime.datetime,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort | None,
) -> None:
    """Close any open SchedulingRequest in this conversation that points at
    the given source appointment. Best-effort."""
    if scheduling_repository is None or source_appointment_id is None:
        return
    requests = scheduling_repository.list_requests_by_conversation(tenant_id, conversation_id)
    for request in requests:
        if (
            request.source_appointment_id == source_appointment_id
            and request.status in _OPEN_SCHEDULING_STATUSES
        ):
            request.set_status("SESSION_CLOSED", now_value)
            request.professional_note = "closed_by_payment_confirmation"
            scheduling_repository.save_request(request)


def _archive_active_subsession(
    conversation: typing.Any,
    tenant_id: str,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
) -> None:
    """Archive the active session of a conversation. No-op if no active
    messages remain."""
    active_messages = conversation_repository.list_messages(tenant_id, conversation.id)
    sorted_messages = sorted(active_messages, key=lambda item: item.created_at)
    conversation.archive_manual_close(messages=sorted_messages, now=now_value)
    conversation_repository.save_conversation(conversation)
    conversation_repository.delete_messages(tenant_id, conversation.id)


def confirm_payment_in_chat_if_open(
    *,
    tenant_id: str,
    whatsapp_user_id: str,
    patient_first_name: str | None,
    source_appointment_id: str | None,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    whatsapp_connection_repository: (
        whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort
    ),
    whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
    id_generator: id_generator_port.IdGeneratorPort,
    clock: clock_port.ClockPort,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort | None = None,
) -> None:
    """Close the chat session tied to a payment, sending a "pago confirmado"
    text only when the patient has a recent INBOUND (Meta's 24h window).

    Always closes any open synthetic SchedulingRequest that points at
    ``source_appointment_id`` and archives the active subsession so the
    conversation moves to Terminadas.

    Never raises: payment approval must not fail because of a chat-side
    glitch.
    """
    del clock  # reserved for future timing decisions, kept in API for symmetry
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        tenant_id, whatsapp_user_id
    )
    if conversation is None:
        logger.info(
            "payment_confirmation.skipped_no_conversation",
            extra={"tenant_id": tenant_id, "whatsapp_user_id": whatsapp_user_id},
        )
        return

    can_send = _has_recent_inbound(conversation.id, tenant_id, now_value, conversation_repository)

    if can_send:
        connection = whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if (
            connection is None
            or connection.access_token is None
            or connection.phone_number_id is None
        ):
            logger.warning(
                "payment_confirmation.whatsapp_not_connected",
                extra={"tenant_id": tenant_id},
            )
        else:
            name = patient_first_name or "Paciente"
            text = f"¡Listo {name}! Tu pago fue confirmado ✅ Te esperamos para tu cita. 🙌"
            try:
                provider_message_id = whatsapp_provider.send_text_message(
                    access_token=connection.access_token,
                    phone_number_id=connection.phone_number_id,
                    whatsapp_user_id=whatsapp_user_id,
                    text=text,
                )
                outbound = message_entity.Message(
                    id=id_generator.new_id(),
                    conversation_id=conversation.id,
                    tenant_id=tenant_id,
                    direction="OUTBOUND",
                    role="assistant",
                    content=text,
                    provider_message_id=provider_message_id,
                    created_at=now_value,
                )
                conversation_repository.save_message(outbound)
            except service_exceptions.ExternalProviderError:
                logger.warning(
                    "payment_confirmation.send_failed",
                    extra={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation.id,
                    },
                    exc_info=True,
                )
    else:
        logger.info(
            "payment_confirmation.skipped_outside_24h_window",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation.id,
                "whatsapp_user_id": whatsapp_user_id,
            },
        )

    # Always close the session: archive subsession + cancel any synthetic
    # request that left the conversation in Pago pendiente / En curso.
    _close_synthetic_request(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        source_appointment_id=source_appointment_id,
        now_value=now_value,
        scheduling_repository=scheduling_repository,
    )
    _archive_active_subsession(
        conversation=conversation,
        tenant_id=tenant_id,
        now_value=now_value,
        conversation_repository=conversation_repository,
    )

    logger.info(
        "payment_confirmation.session_closed",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="payment_confirmation.session_closed",
                message=f"payment session closed (notification sent: {can_send})",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation.id,
                    "notification_sent": can_send,
                    "source_appointment_id": source_appointment_id,
                },
            )
        },
    )
