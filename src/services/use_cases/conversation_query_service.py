import src.ports.conversation_repository_port as conversation_repository_port
import src.services.dto.conversation_dto as conversation_dto
import src.services.exceptions as service_exceptions


class ConversationQueryService:
    def __init__(
        self,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    ) -> None:
        self._conversation_repository = conversation_repository

    def list_conversations(self, tenant_id: str) -> conversation_dto.ConversationListResponseDTO:
        conversations = self._conversation_repository.list_conversations(tenant_id)
        sorted_conversations = sorted(conversations, key=lambda item: item.updated_at, reverse=True)

        items: list[conversation_dto.ConversationSummaryDTO] = []
        for conversation in sorted_conversations:
            item = conversation_dto.ConversationSummaryDTO(
                conversation_id=conversation.id,
                whatsapp_user_id=conversation.whatsapp_user_id,
                last_message_preview=conversation.last_message_preview,
                updated_at=conversation.updated_at,
                control_mode=conversation.control_mode,
            )
            items.append(item)

        return conversation_dto.ConversationListResponseDTO(items=items)

    def list_messages(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> conversation_dto.MessageListResponseDTO:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        messages = self._conversation_repository.list_messages(tenant_id, conversation_id)
        sorted_messages = sorted(messages, key=lambda item: item.created_at)

        items: list[conversation_dto.MessageDTO] = []
        for message in sorted_messages:
            item = conversation_dto.MessageDTO(
                message_id=message.id,
                conversation_id=message.conversation_id,
                role=message.role,
                direction=message.direction,
                content=message.content,
                created_at=message.created_at,
            )
            items.append(item)

        return conversation_dto.MessageListResponseDTO(items=items)
