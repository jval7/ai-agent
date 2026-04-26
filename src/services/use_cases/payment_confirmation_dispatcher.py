"""Send a 'pago confirmado' freeform message to the patient and close the
session, IF a chat conversation is open within Meta's 24h freeform window.

Both the manual payment update flow (manual_appointment_service.update_payment)
and the post-reminder payment approval flow
(scheduling_service._approve_payment_from_reminder) call this helper so the
patient experience is identical regardless of which UI tab triggered the
approval.

Outside the 24h window (or if the patient never chatted), no freeform text
is sent — Meta would reject it. The reminder swap PAYMENT->ATTENDANCE
already covers the notification when the next reminder fires.
"""

import datetime

import src.domain.entities.message as message_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)

_FREEFORM_WINDOW = datetime.timedelta(hours=24)


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


def confirm_payment_in_chat_if_open(
    *,
    tenant_id: str,
    whatsapp_user_id: str,
    patient_first_name: str | None,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    whatsapp_connection_repository: (
        whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort
    ),
    whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
    id_generator: id_generator_port.IdGeneratorPort,
    clock: clock_port.ClockPort,
) -> None:
    """If the patient has an open chat with a recent INBOUND, send a
    'pago confirmado' message and archive the session. Otherwise log and
    return — never raises so payment approval cannot fail because of a
    chat-side glitch."""
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

    if not _has_recent_inbound(conversation.id, tenant_id, now_value, conversation_repository):
        logger.info(
            "payment_confirmation.skipped_outside_24h_window",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation.id,
                "whatsapp_user_id": whatsapp_user_id,
            },
        )
        return

    connection = whatsapp_connection_repository.get_by_tenant_id(tenant_id)
    if connection is None or connection.access_token is None or connection.phone_number_id is None:
        logger.warning(
            "payment_confirmation.whatsapp_not_connected",
            extra={"tenant_id": tenant_id},
        )
        return

    name = patient_first_name or "Paciente"
    text = f"¡Listo {name}! Tu pago fue confirmado ✅ Te esperamos para tu cita. 🙌"
    try:
        provider_message_id = whatsapp_provider.send_text_message(
            access_token=connection.access_token,
            phone_number_id=connection.phone_number_id,
            whatsapp_user_id=whatsapp_user_id,
            text=text,
        )
    except service_exceptions.ExternalProviderError:
        logger.warning(
            "payment_confirmation.send_failed",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation.id,
            },
            exc_info=True,
        )
        return

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

    # Archive the active session so the conversation card moves to
    # Terminadas — same UX as scheduling.session_close.
    active_messages = conversation_repository.list_messages(tenant_id, conversation.id)
    sorted_messages = sorted(active_messages, key=lambda item: item.created_at)
    conversation.archive_manual_close(messages=sorted_messages, now=now_value)
    conversation_repository.save_conversation(conversation)
    conversation_repository.delete_messages(tenant_id, conversation.id)

    logger.info(
        "payment_confirmation.sent",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="payment_confirmation.sent",
                message="payment confirmation message sent and session archived",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation.id,
                    "provider_message_id": provider_message_id,
                },
            )
        },
    )
