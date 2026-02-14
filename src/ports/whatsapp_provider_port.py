import abc
import typing

import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto


class WhatsappProviderPort(abc.ABC):
    @abc.abstractmethod
    def build_embedded_signup_url(self, state: str) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def exchange_code_for_credentials(self, code: str) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def send_text_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def parse_incoming_message_events(
        self, payload: dict[str, typing.Any]
    ) -> list[webhook_dto.IncomingMessageEventDTO]:
        raise NotImplementedError
