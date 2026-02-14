import abc

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity


class ConversationRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save_whatsapp_user(self, whatsapp_user: whatsapp_user_entity.WhatsappUser) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_whatsapp_user(
        self, tenant_id: str, whatsapp_user_id: str
    ) -> whatsapp_user_entity.WhatsappUser | None:
        raise NotImplementedError

    @abc.abstractmethod
    def save_conversation(self, conversation: conversation_entity.Conversation) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_conversation_by_whatsapp_user(
        self, tenant_id: str, whatsapp_user_id: str
    ) -> conversation_entity.Conversation | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_conversation_by_id(
        self, tenant_id: str, conversation_id: str
    ) -> conversation_entity.Conversation | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_conversations(self, tenant_id: str) -> list[conversation_entity.Conversation]:
        raise NotImplementedError

    @abc.abstractmethod
    def save_message(self, message: message_entity.Message) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_messages(self, tenant_id: str, conversation_id: str) -> list[message_entity.Message]:
        raise NotImplementedError
