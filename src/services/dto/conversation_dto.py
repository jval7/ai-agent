import datetime
import typing

import pydantic

import src.services.dto.tag_dto as tag_dto


class ConversationSummaryDTO(pydantic.BaseModel):
    conversation_id: str
    whatsapp_user_id: str
    contact_name: str | None
    last_message_preview: str | None
    updated_at: datetime.datetime
    control_mode: typing.Literal["AI", "HUMAN"]
    tag_ids: list[str] = pydantic.Field(default_factory=list)
    tags: list[tag_dto.TagDTO] = pydantic.Field(default_factory=list)


class SetContactNameToolInputDTO(pydantic.BaseModel):
    contact_name: str


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


class SendProfessionalMessageDTO(pydantic.BaseModel):
    message_text: str


class MessageSentResponseDTO(pydantic.BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime.datetime
