import datetime
import typing

import pydantic


class ConversationSummaryDTO(pydantic.BaseModel):
    conversation_id: str
    whatsapp_user_id: str
    last_message_preview: str | None
    updated_at: datetime.datetime
    control_mode: typing.Literal["AI", "HUMAN"]


class MessageDTO(pydantic.BaseModel):
    message_id: str
    conversation_id: str
    role: str
    direction: str
    content: str
    created_at: datetime.datetime


class ConversationListResponseDTO(pydantic.BaseModel):
    items: list[ConversationSummaryDTO]


class MessageListResponseDTO(pydantic.BaseModel):
    items: list[MessageDTO]


class UpdateConversationControlModeDTO(pydantic.BaseModel):
    control_mode: typing.Literal["AI", "HUMAN"]


class ConversationControlModeResponseDTO(pydantic.BaseModel):
    conversation_id: str
    tenant_id: str
    control_mode: typing.Literal["AI", "HUMAN"]
    updated_at: datetime.datetime
