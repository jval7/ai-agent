import abc

import src.domain.entities.whatsapp_connection as whatsapp_connection_entity


class WhatsappConnectionRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, connection: whatsapp_connection_entity.WhatsappConnection) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_tenant_id(
        self, tenant_id: str
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_phone_number_id(
        self, phone_number_id: str
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_embedded_signup_state(
        self, embedded_signup_state: str
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        raise NotImplementedError
