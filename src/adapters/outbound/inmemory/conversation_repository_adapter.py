import datetime

import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.ports.conversation_repository_port as conversation_repository_port


class InMemoryConversationRepositoryAdapter(
    conversation_repository_port.ConversationRepositoryPort
):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save_whatsapp_user(self, whatsapp_user: whatsapp_user_entity.WhatsappUser) -> None:
        with self._store.lock:
            key = (whatsapp_user.tenant_id, whatsapp_user.id)
            self._store.whatsapp_user_by_tenant_and_id[key] = whatsapp_user.model_copy(deep=True)
            self._store.flush()

    def get_whatsapp_user(
        self, tenant_id: str, whatsapp_user_id: str
    ) -> whatsapp_user_entity.WhatsappUser | None:
        with self._store.lock:
            key = (tenant_id, whatsapp_user_id)
            whatsapp_user = self._store.whatsapp_user_by_tenant_and_id.get(key)
            if whatsapp_user is None:
                return None
            return whatsapp_user.model_copy(deep=True)

    def list_whatsapp_users(self, tenant_id: str) -> list[whatsapp_user_entity.WhatsappUser]:
        with self._store.lock:
            users: list[whatsapp_user_entity.WhatsappUser] = []
            for (stored_tenant_id, _), user in self._store.whatsapp_user_by_tenant_and_id.items():
                if stored_tenant_id == tenant_id:
                    users.append(user.model_copy(deep=True))
            return users

    def save_conversation(self, conversation: conversation_entity.Conversation) -> None:
        with self._store.lock:
            key = (conversation.tenant_id, conversation.whatsapp_user_id)
            conversation_copy = conversation.model_copy(deep=True)
            existing_conversation = self._store.conversation_by_id.get(conversation.id)
            if existing_conversation is not None:
                conversation_copy.messages = [
                    message.model_copy(deep=True) for message in existing_conversation.messages
                ]
            self._store.conversation_by_tenant_and_wa_user[key] = conversation_copy
            self._store.conversation_by_id[conversation.id] = conversation_copy
            self._store.messages_by_conversation_id[conversation.id] = [
                message.model_copy(deep=True) for message in conversation_copy.messages
            ]
            self._store.flush()

    def get_conversation_by_whatsapp_user(
        self, tenant_id: str, whatsapp_user_id: str
    ) -> conversation_entity.Conversation | None:
        with self._store.lock:
            key = (tenant_id, whatsapp_user_id)
            conversation = self._store.conversation_by_tenant_and_wa_user.get(key)
            if conversation is None:
                return None
            return conversation.model_copy(deep=True)

    def get_conversation_by_id(
        self, tenant_id: str, conversation_id: str
    ) -> conversation_entity.Conversation | None:
        with self._store.lock:
            conversation = self._store.conversation_by_id.get(conversation_id)
            if conversation is None:
                return None
            if conversation.tenant_id != tenant_id:
                return None
            return conversation.model_copy(deep=True)

    def list_conversations(self, tenant_id: str) -> list[conversation_entity.Conversation]:
        with self._store.lock:
            conversations: list[conversation_entity.Conversation] = []
            for conversation in self._store.conversation_by_id.values():
                if conversation.tenant_id == tenant_id:
                    conversations.append(conversation.model_copy(deep=True))
            return conversations

    def count_conversations(self, tenant_id: str) -> int:
        with self._store.lock:
            return sum(
                1 for conv in self._store.conversation_by_id.values() if conv.tenant_id == tenant_id
            )

    def count_active_since(self, tenant_id: str, since: datetime.datetime) -> int:
        with self._store.lock:
            return sum(
                1
                for conv in self._store.conversation_by_id.values()
                if conv.tenant_id == tenant_id
                and conv.updated_at is not None
                and conv.updated_at >= since
            )

    def get_latest_activity(self, tenant_id: str) -> datetime.datetime | None:
        with self._store.lock:
            latest: datetime.datetime | None = None
            for conv in self._store.conversation_by_id.values():
                if conv.tenant_id != tenant_id:
                    continue
                if conv.updated_at is None:
                    continue
                if latest is None or conv.updated_at > latest:
                    latest = conv.updated_at
            return latest

    def save_message(self, message: message_entity.Message) -> None:
        with self._store.lock:
            conversation = self._store.conversation_by_id.get(message.conversation_id)
            if conversation is None or conversation.tenant_id != message.tenant_id:
                raise ValueError("conversation not found for message")
            updated_conversation = conversation.model_copy(deep=True)
            updated_message = message.model_copy(deep=True)
            updated_conversation.messages.append(updated_message)
            conversation_key = (
                updated_conversation.tenant_id,
                updated_conversation.whatsapp_user_id,
            )
            self._store.conversation_by_id[updated_conversation.id] = updated_conversation
            self._store.conversation_by_tenant_and_wa_user[conversation_key] = updated_conversation
            self._store.messages_by_conversation_id[updated_conversation.id] = [
                stored_message.model_copy(deep=True)
                for stored_message in updated_conversation.messages
            ]
            self._store.flush()

    def list_messages(self, tenant_id: str, conversation_id: str) -> list[message_entity.Message]:
        with self._store.lock:
            conversation = self._store.conversation_by_id.get(conversation_id)
            if conversation is None or conversation.tenant_id != tenant_id:
                return []
            if conversation.messages:
                return [message.model_copy(deep=True) for message in conversation.messages]
            message_list = self._store.messages_by_conversation_id.get(conversation_id, [])
            return [message.model_copy(deep=True) for message in message_list]

    def delete_messages(self, tenant_id: str, conversation_id: str) -> None:
        with self._store.lock:
            conversation = self._store.conversation_by_id.get(conversation_id)
            if conversation is None or conversation.tenant_id != tenant_id:
                return
            updated_conversation = conversation.model_copy(deep=True)
            updated_conversation.messages = []
            conversation_key = (
                updated_conversation.tenant_id,
                updated_conversation.whatsapp_user_id,
            )
            self._store.conversation_by_id[updated_conversation.id] = updated_conversation
            self._store.conversation_by_tenant_and_wa_user[conversation_key] = updated_conversation
            self._store.messages_by_conversation_id[conversation_id] = []
            self._store.flush()

    def delete_conversation(self, tenant_id: str, conversation_id: str) -> None:
        with self._store.lock:
            conversation = self._store.conversation_by_id.get(conversation_id)
            if conversation is None or conversation.tenant_id != tenant_id:
                return
            conversation_key = (conversation.tenant_id, conversation.whatsapp_user_id)
            self._store.conversation_by_id.pop(conversation_id, None)
            self._store.conversation_by_tenant_and_wa_user.pop(conversation_key, None)
            self._store.messages_by_conversation_id.pop(conversation_id, None)
            self._store.flush()

    def delete_whatsapp_user(self, tenant_id: str, whatsapp_user_id: str) -> None:
        with self._store.lock:
            key = (tenant_id, whatsapp_user_id)
            self._store.whatsapp_user_by_tenant_and_id.pop(key, None)
            self._store.flush()
