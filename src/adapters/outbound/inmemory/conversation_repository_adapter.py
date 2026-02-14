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

    def save_conversation(self, conversation: conversation_entity.Conversation) -> None:
        with self._store.lock:
            key = (conversation.tenant_id, conversation.whatsapp_user_id)
            conversation_copy = conversation.model_copy(deep=True)
            self._store.conversation_by_tenant_and_wa_user[key] = conversation_copy
            self._store.conversation_by_id[conversation.id] = conversation_copy
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

    def save_message(self, message: message_entity.Message) -> None:
        with self._store.lock:
            conversation_messages = self._store.messages_by_conversation_id.get(
                message.conversation_id
            )
            if conversation_messages is None:
                conversation_messages = []
                self._store.messages_by_conversation_id[message.conversation_id] = (
                    conversation_messages
                )
            conversation_messages.append(message.model_copy(deep=True))
            self._store.flush()

    def list_messages(self, tenant_id: str, conversation_id: str) -> list[message_entity.Message]:
        with self._store.lock:
            conversation = self._store.conversation_by_id.get(conversation_id)
            if conversation is None or conversation.tenant_id != tenant_id:
                return []
            message_list = self._store.messages_by_conversation_id.get(conversation_id, [])
            return [message.model_copy(deep=True) for message in message_list]
