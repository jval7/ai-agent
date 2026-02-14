import datetime

import pydantic


class ConversationSummaryDTO(pydantic.BaseModel):
    conversation_id: str
    whatsapp_user_id: str
    last_message_preview: str | None
    updated_at: datetime.datetime


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
