"""Wrapper que delega todo al adapter real. En send_text_message,
consulta settings.whatsapp_outbound_noop en runtime para decidir
si envía realmente o retorna un ID sintético."""

from __future__ import annotations

import logging
import typing
import uuid

import src.infra.settings as app_settings
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto

logger = logging.getLogger(__name__)


class NoopWhatsappSendAdapter(whatsapp_provider_port.WhatsappProviderPort):
    def __init__(
        self,
        delegate: whatsapp_provider_port.WhatsappProviderPort,
        settings: app_settings.Settings,
    ) -> None:
        self._delegate = delegate
        self._settings = settings

    def build_embedded_signup_url(self, state: str) -> str:
        return self._delegate.build_embedded_signup_url(state)

    def exchange_code_for_credentials(
        self,
        code: str,
        *,
        from_js_sdk: bool = False,
        js_sdk_origin_url: str | None = None,
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        return self._delegate.exchange_code_for_credentials(
            code, from_js_sdk=from_js_sdk, js_sdk_origin_url=js_sdk_origin_url
        )

    def resolve_credentials_from_token(
        self, access_token: str
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        return self._delegate.resolve_credentials_from_token(access_token)

    def subscribe_app_to_waba(self, access_token: str, business_account_id: str) -> None:
        self._delegate.subscribe_app_to_waba(access_token, business_account_id)

    def register_phone_number(
        self, access_token: str, phone_number_id: str, registration_pin: str | None = None
    ) -> None:
        self._delegate.register_phone_number(access_token, phone_number_id, registration_pin)

    def send_text_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        if not self._settings.whatsapp_outbound_noop:
            return self._delegate.send_text_message(
                access_token, phone_number_id, whatsapp_user_id, text
            )
        synthetic_id = f"noop-{uuid.uuid4().hex[:12]}"
        logger.info(
            "noop_whatsapp_send",
            extra={
                "whatsapp_user_id": whatsapp_user_id,
                "synthetic_message_id": synthetic_id,
                "text_length": len(text),
            },
        )
        return synthetic_id

    def parse_incoming_message_events(
        self, payload: dict[str, typing.Any]
    ) -> list[webhook_dto.IncomingMessageEventDTO]:
        return self._delegate.parse_incoming_message_events(payload)

    def list_message_templates(
        self, access_token: str, waba_id: str
    ) -> list[whatsapp_template_dto.TemplateDTO]:
        return self._delegate.list_message_templates(access_token, waba_id)

    def create_message_template(
        self,
        access_token: str,
        waba_id: str,
        template: whatsapp_template_dto.CreateTemplateRequestDTO,
    ) -> whatsapp_template_dto.TemplateDTO:
        return self._delegate.create_message_template(access_token, waba_id, template)

    def delete_message_template(self, access_token: str, waba_id: str, template_name: str) -> None:
        self._delegate.delete_message_template(access_token, waba_id, template_name)

    def send_template_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> str:
        if not self._settings.whatsapp_outbound_noop:
            return self._delegate.send_template_message(
                access_token,
                phone_number_id,
                whatsapp_user_id,
                template_name,
                language_code,
                body_parameters,
            )
        synthetic_id = f"noop-template-{uuid.uuid4().hex[:12]}"
        logger.info(
            "noop_whatsapp_send_template",
            extra={
                "whatsapp_user_id": whatsapp_user_id,
                "template_name": template_name,
                "synthetic_message_id": synthetic_id,
            },
        )
        return synthetic_id
