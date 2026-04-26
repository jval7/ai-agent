"""Helper to ensure a WhatsappUser + Conversation exist for a given tenant.

Both the inbound webhook flow (first contact from the patient) and the
reminder pre-positioning flow (template send to a patient who never chatted
before) need to materialize the (whatsapp_user, conversation) pair if it
does not exist yet. This module centralizes that logic so the two callers
stay in sync.
"""

import datetime

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port


def ensure_conversation_for_whatsapp_user(
    *,
    tenant_id: str,
    whatsapp_user_id: str,
    display_name: str | None,
    now_value: datetime.datetime,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    id_generator: id_generator_port.IdGeneratorPort,
) -> tuple[whatsapp_user_entity.WhatsappUser, conversation_entity.Conversation]:
    """Return the WhatsappUser and Conversation for the given pair, creating
    either one if it does not exist yet."""
    whatsapp_user = conversation_repository.get_whatsapp_user(tenant_id, whatsapp_user_id)
    if whatsapp_user is None:
        whatsapp_user = whatsapp_user_entity.WhatsappUser(
            id=whatsapp_user_id,
            tenant_id=tenant_id,
            display_name=display_name,
            created_at=now_value,
        )
        conversation_repository.save_whatsapp_user(whatsapp_user)

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        tenant_id, whatsapp_user_id
    )
    if conversation is None:
        conversation = conversation_entity.Conversation(
            id=id_generator.new_id(),
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
        conversation_repository.save_conversation(conversation)

    return whatsapp_user, conversation
