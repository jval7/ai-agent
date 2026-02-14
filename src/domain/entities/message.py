import datetime
import typing

import pydantic


class Message(pydantic.BaseModel):
    id: str
    conversation_id: str
    tenant_id: str
    direction: typing.Literal["INBOUND", "OUTBOUND"]
    role: typing.Literal["user", "assistant", "system"]
    content: str
    provider_message_id: str | None
    created_at: datetime.datetime

    @pydantic.field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("message content cannot be empty")
        return normalized_value
