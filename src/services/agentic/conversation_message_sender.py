import src.domain.entities.message as message_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class ConversationMessageSender:
    def __init__(
        self,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._whatsapp_provider = whatsapp_provider
        self._conversation_repository = conversation_repository
        self._id_generator = id_generator
        self._clock = clock

    def send_assistant_message(
        self,
        connection: whatsapp_connection_entity.WhatsappConnection,
        conversation_id: str,
        tenant_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        if connection.access_token is None or connection.phone_number_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")
        outbound_message_provider_id = self._whatsapp_provider.send_text_message(
            access_token=connection.access_token,
            phone_number_id=connection.phone_number_id,
            whatsapp_user_id=whatsapp_user_id,
            text=text,
        )
        outbound_message = message_entity.Message(
            id=self._id_generator.new_id(),
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            direction="OUTBOUND",
            role="assistant",
            content=text,
            provider_message_id=outbound_message_provider_id,
            created_at=self._clock.now(),
        )
        self._conversation_repository.save_message(outbound_message)
        latest_conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if latest_conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")
        latest_conversation.append_message(
            outbound_message.id,
            outbound_message.content,
            outbound_message.created_at,
        )
        self._conversation_repository.save_conversation(latest_conversation)
        return outbound_message_provider_id

    def archive_messages_into_subsession_if_booking_occurred(
        self,
        tenant_id: str,
        conversation_id: str,
        subsessions_count_before_ai_reply: int,
    ) -> None:
        latest_conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id,
            conversation_id,
        )
        if latest_conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        if len(latest_conversation.subsessions) <= subsessions_count_before_ai_reply:
            return

        latest_subsession = latest_conversation.subsessions[-1]
        active_messages = self._conversation_repository.list_messages(
            tenant_id,
            conversation_id,
        )
        if not active_messages:
            return

        sorted_active_messages = sorted(active_messages, key=lambda item: item.created_at)
        existing_message_ids = {message.id for message in latest_subsession.messages}
        appended_messages_count = 0
        for active_message in sorted_active_messages:
            if active_message.id in existing_message_ids:
                continue
            latest_subsession.messages.append(active_message.model_copy(deep=True))
            existing_message_ids.add(active_message.id)
            appended_messages_count += 1

        latest_conversation.messages = []
        latest_conversation.message_ids = []
        latest_conversation.last_message_preview = None
        latest_conversation.updated_at = self._clock.now()
        self._conversation_repository.save_conversation(latest_conversation)
        self._conversation_repository.delete_messages(tenant_id, conversation_id)
        logger.info(
            "webhook.booking_confirmation_message_archived",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.booking_confirmation_message_archived",
                    message=(
                        "booking confirmation message archived into latest booking subsession"
                    ),
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "appended_messages_count": appended_messages_count,
                        "subsessions_count": len(latest_conversation.subsessions),
                    },
                )
            },
        )
