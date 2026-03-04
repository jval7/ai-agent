import datetime
import typing

import pydantic

import src.domain.entities.message as message_entity


class ConversationSubsession(pydantic.BaseModel):
    archived_at: datetime.datetime
    archived_reason: typing.Literal["APPOINTMENT_BOOKED"]
    scheduling_request_id: str
    calendar_event_id: str
    messages: list[message_entity.Message]


class Conversation(pydantic.BaseModel):
    id: str
    tenant_id: str
    whatsapp_user_id: str
    started_at: datetime.datetime
    updated_at: datetime.datetime
    last_message_preview: str | None
    message_ids: list[str]
    messages: list[message_entity.Message] = pydantic.Field(default_factory=list)
    control_mode: typing.Literal["AI", "HUMAN"] = "AI"
    subsessions: list[ConversationSubsession] = pydantic.Field(default_factory=list)

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

    def archive_current_session(
        self,
        scheduling_request_id: str,
        calendar_event_id: str,
        messages: list[message_entity.Message],
        now: datetime.datetime,
    ) -> None:
        active_messages = [message.model_copy(deep=True) for message in messages]
        if not active_messages:
            active_messages = [message.model_copy(deep=True) for message in self.messages]

        if not active_messages:
            self.message_ids = []
            self.messages = []
            self.last_message_preview = None
            self.updated_at = now
            return

        session_snapshot = ConversationSubsession(
            archived_at=now,
            archived_reason="APPOINTMENT_BOOKED",
            scheduling_request_id=scheduling_request_id,
            calendar_event_id=calendar_event_id,
            messages=active_messages,
        )
        self.subsessions.append(session_snapshot)
        self.message_ids = []
        self.messages = []
        self.last_message_preview = None
        self.updated_at = now
