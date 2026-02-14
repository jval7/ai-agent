import datetime
import typing

import pydantic


class Conversation(pydantic.BaseModel):
    id: str
    tenant_id: str
    whatsapp_user_id: str
    started_at: datetime.datetime
    updated_at: datetime.datetime
    last_message_preview: str | None
    message_ids: list[str]
    control_mode: typing.Literal["AI", "HUMAN"] = "AI"

    def append_message(self, message_id: str, preview: str, now: datetime.datetime) -> None:
        self.message_ids.append(message_id)
        self.last_message_preview = preview[:120]
        self.updated_at = now

    def set_control_mode(
        self,
        control_mode: typing.Literal["AI", "HUMAN"],
        now: datetime.datetime,
    ) -> None:
        self.control_mode = control_mode
        self.updated_at = now
