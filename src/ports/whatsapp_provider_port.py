import abc
import typing

import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto


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
    def resolve_credentials_from_token(
        self, access_token: str
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

    @abc.abstractmethod
    def list_message_templates(
        self, access_token: str, waba_id: str
    ) -> list[whatsapp_template_dto.TemplateDTO]:
        raise NotImplementedError

    @abc.abstractmethod
    def create_message_template(
        self,
        access_token: str,
        waba_id: str,
        template: whatsapp_template_dto.CreateTemplateRequestDTO,
    ) -> whatsapp_template_dto.TemplateDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_message_template(self, access_token: str, waba_id: str, template_name: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def send_template_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def send_hello_world_preflight(
        self,
        access_token: str,
        phone_number_id: str,
        recipient_phone_e164: str,
    ) -> str:
        """Send Meta's pre-approved `hello_world` template as a billing preflight.

        Returns the outbound message id on success. On Meta error 131042 raises
        `WhatsappBillingNotConfiguredError`. On other Meta errors raises
        `WhatsappPreflightError` with the parsed `meta_error_code`.
        """
        raise NotImplementedError
