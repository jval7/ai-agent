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
        "AWAITING_CONSULTATION_REVIEW",
        "AWAITING_CONSULTATION_DETAILS",
        "AWAITING_PROFESSIONAL_SLOTS",
        "AWAITING_PATIENT_CHOICE",
        "CONSULTATION_REJECTED",
        "CANCELLED",
        "BOOKED",
        "HUMAN_HANDOFF",
    ]
    round_number: int
    patient_preference_note: str | None
    rejection_summary: str | None
    professional_note: str | None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_age: int | None = None
    consultation_reason: str | None = None
    consultation_details: str | None = None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None = None
    patient_location: str | None = None
    slots: list[scheduling_slot_entity.SchedulingSlot]
    slot_options_map: dict[str, str]
    selected_slot_id: str | None
    calendar_event_id: str | None
    payment_amount_cop: int | None = None
    payment_method: typing.Literal["CASH", "TRANSFER"] | None = None
    payment_status: typing.Literal["PENDING", "PAID"] = "PENDING"
    payment_updated_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @pydantic.field_validator("patient_preference_note")
    @classmethod
    def validate_patient_preference_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @pydantic.field_validator("round_number")
    @classmethod
    def validate_round_number(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("round_number must be greater than zero")
        return value

    @pydantic.field_validator("payment_amount_cop")
    @classmethod
    def validate_payment_amount_cop(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("payment_amount_cop must be greater than zero")
        return value

    def set_status(
        self,
        status: typing.Literal[
            "COLLECTING_PREFERENCES",
            "AWAITING_CONSULTATION_REVIEW",
            "AWAITING_CONSULTATION_DETAILS",
            "AWAITING_PROFESSIONAL_SLOTS",
            "AWAITING_PATIENT_CHOICE",
            "CONSULTATION_REJECTED",
            "CANCELLED",
            "BOOKED",
            "HUMAN_HANDOFF",
        ],
        now: datetime.datetime,
    ) -> None:
        self.status = status
        self.updated_at = now
