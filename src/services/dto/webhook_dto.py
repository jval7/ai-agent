import typing

import pydantic


class WebhookVerificationDTO(pydantic.BaseModel):
    mode: str
    verify_token: str
    challenge: str


class IncomingMessageEventDTO(pydantic.BaseModel):
    provider_event_id: str
    phone_number_id: str
    whatsapp_user_id: str
    whatsapp_user_name: str | None
    message_id: str
    message_type: str
    source: typing.Literal["CUSTOMER", "PROFESSIONAL_APP"]
    message_text: str


class MessageStatusEventDTO(pydantic.BaseModel):
    """Outbound message status callback emitted by the WhatsApp provider.

    Meta's Cloud API sends a `statuses[]` array on the same webhook used for
    inbound messages, reporting the lifecycle of a previously-sent message
    (sent / delivered / read / failed). When `status == "failed"` the payload
    also includes an `errors[]` array describing why delivery failed.
    """

    provider_event_id: str
    phone_number_id: str
    provider_message_id: str
    recipient_id: str
    status: typing.Literal["sent", "delivered", "read", "failed"]
    timestamp_epoch_seconds: int | None = None
    error_code: int | None = None
    error_title: str | None = None
    error_message: str | None = None


class WebhookEventResponseDTO(pydantic.BaseModel):
    status: str
