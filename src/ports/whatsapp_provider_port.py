import abc
import typing

import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto


class WhatsappProviderPort(abc.ABC):
    @abc.abstractmethod
    def build_embedded_signup_url(self, state: str) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def exchange_code_for_credentials(
        self,
        code: str,
        *,
        from_js_sdk: bool = False,
        js_sdk_origin_url: str | None = None,
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe_app_to_waba(self, access_token: str, business_account_id: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def register_phone_number(
        self, access_token: str, phone_number_id: str, registration_pin: str | None = None
    ) -> None:
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
