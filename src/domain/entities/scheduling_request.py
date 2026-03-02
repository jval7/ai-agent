import datetime
import typing

import pydantic

import src.domain.entities.scheduling_slot as scheduling_slot_entity


class SchedulingRequest(pydantic.BaseModel):
    id: str
    tenant_id: str
    conversation_id: str
    whatsapp_user_id: str
    request_kind: typing.Literal["INITIAL", "RETRY"]
    status: typing.Literal[
        "COLLECTING_PREFERENCES",
        "AWAITING_PROFESSIONAL_SLOTS",
        "AWAITING_PATIENT_CHOICE",
        "BOOKED",
        "HUMAN_HANDOFF",
    ]
    round_number: int
    patient_preference_note: str
    rejection_summary: str | None
    professional_note: str | None
    slots: list[scheduling_slot_entity.SchedulingSlot]
    slot_options_map: dict[str, str]
    selected_slot_id: str | None
    calendar_event_id: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @pydantic.field_validator("patient_preference_note")
    @classmethod
    def validate_patient_preference_note(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("patient_preference_note cannot be empty")
        return normalized_value

    @pydantic.field_validator("round_number")
    @classmethod
    def validate_round_number(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("round_number must be greater than zero")
        return value

    def set_status(
        self,
        status: typing.Literal[
            "COLLECTING_PREFERENCES",
            "AWAITING_PROFESSIONAL_SLOTS",
            "AWAITING_PATIENT_CHOICE",
            "BOOKED",
            "HUMAN_HANDOFF",
        ],
        now: datetime.datetime,
    ) -> None:
        self.status = status
        self.updated_at = now
