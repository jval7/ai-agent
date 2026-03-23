"""Wrapper que delega todo al adapter real excepto send_text_message,
que simplemente retorna un ID sintetico sin llamar a Meta."""

from __future__ import annotations

import logging
import typing
import uuid

import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto

logger = logging.getLogger(__name__)


class NoopWhatsappSendAdapter(whatsapp_provider_port.WhatsappProviderPort):
    def __init__(self, delegate: whatsapp_provider_port.WhatsappProviderPort) -> None:
        self._delegate = delegate

    def build_embedded_signup_url(self, state: str) -> str:
        return self._delegate.build_embedded_signup_url(state)

    def exchange_code_for_credentials(self, code: str) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        return self._delegate.exchange_code_for_credentials(code)

    def subscribe_app_to_waba(self, access_token: str, business_account_id: str) -> None:
        self._delegate.subscribe_app_to_waba(access_token, business_account_id)

    def register_phone_number(self, access_token: str, phone_number_id: str) -> None:
        self._delegate.register_phone_number(access_token, phone_number_id)

    def send_text_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
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
