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
    source: typing.Literal["CUSTOMER", "OWNER_APP"]
    message_text: str


class WebhookEventResponseDTO(pydantic.BaseModel):
    status: str
