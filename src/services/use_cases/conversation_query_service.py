import src.domain.entities.tag as tag_entity
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.tag_repository_port as tag_repository_port
import src.services.dto.conversation_dto as conversation_dto
import src.services.dto.tag_dto as tag_dto
import src.services.exceptions as service_exceptions


class ConversationQueryService:
    def __init__(
        self,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        tag_repository: tag_repository_port.TagRepositoryPort,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._tag_repository = tag_repository

    def list_conversations(self, tenant_id: str) -> conversation_dto.ConversationListResponseDTO:
        conversations = self._conversation_repository.list_conversations(tenant_id)
        sorted_conversations = sorted(conversations, key=lambda item: item.updated_at, reverse=True)

        whatsapp_users = self._conversation_repository.list_whatsapp_users(tenant_id)
        display_name_by_user_id = {user.id: user.display_name for user in whatsapp_users}

        tenant_tags = self._tag_repository.list_by_tenant(tenant_id)
        tag_by_id: dict[str, tag_entity.Tag] = {tag.id: tag for tag in tenant_tags}

        items: list[conversation_dto.ConversationSummaryDTO] = []
        for conversation in sorted_conversations:
            conversation_tag_dtos: list[tag_dto.TagDTO] = []
            for tag_id in conversation.tag_ids:
                tag = tag_by_id.get(tag_id)
                if tag is None:
                    continue
                conversation_tag_dtos.append(self._to_tag_dto(tag))
            item = conversation_dto.ConversationSummaryDTO(
                conversation_id=conversation.id,
                whatsapp_user_id=conversation.whatsapp_user_id,
                contact_name=display_name_by_user_id.get(conversation.whatsapp_user_id),
                last_message_preview=conversation.last_message_preview,
                updated_at=conversation.updated_at,
                control_mode=conversation.control_mode,
                tag_ids=list(conversation.tag_ids),
                tags=conversation_tag_dtos,
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

        if not messages and conversation.subsessions:
            messages = list(conversation.subsessions[-1].messages)

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

    def _to_tag_dto(self, tag: tag_entity.Tag) -> tag_dto.TagDTO:
        return tag_dto.TagDTO(
            id=tag.id,
            tenant_id=tag.tenant_id,
            name=tag.name,
            slug=tag.slug,
            color=tag.color,
            tag_type=tag.tag_type,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
        )
