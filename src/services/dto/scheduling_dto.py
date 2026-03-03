import datetime
import typing

import pydantic


class SchedulingSlotDTO(pydantic.BaseModel):
    slot_id: str
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    status: str


class SchedulingRequestSummaryDTO(pydantic.BaseModel):
    request_id: str
    conversation_id: str
    whatsapp_user_id: str
    request_kind: str
    status: str
    round_number: int
    patient_preference_note: str | None
    rejection_summary: str | None
    professional_note: str | None
    patient_first_name: str | None
    patient_last_name: str | None
    patient_age: int | None
    consultation_reason: str | None
    consultation_details: str | None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None
    patient_location: str | None
    slot_options_map: dict[str, str]
    selected_slot_id: str | None
    calendar_event_id: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    slots: list[SchedulingSlotDTO]


class SchedulingRequestListResponseDTO(pydantic.BaseModel):
    items: list[SchedulingRequestSummaryDTO]


class ProfessionalSlotInputDTO(pydantic.BaseModel):
    slot_id: str
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str

    @pydantic.model_validator(mode="after")
    def validate_range(self) -> "ProfessionalSlotInputDTO":
        if self.end_at <= self.start_at:
            raise ValueError("slot end_at must be greater than start_at")
        return self


class ProfessionalSubmitSlotsDTO(pydantic.BaseModel):
    slots: list[ProfessionalSlotInputDTO]
    professional_note: str | None

    @pydantic.field_validator("slots")
    @classmethod
    def validate_slots(
        cls, value: list[ProfessionalSlotInputDTO]
    ) -> list[ProfessionalSlotInputDTO]:
        if not value:
            raise ValueError("at least one slot is required")
        return value


class ProfessionalSubmitSlotsResponseDTO(pydantic.BaseModel):
    status: typing.Literal["AWAITING_PATIENT_CHOICE"]
    slot_batch_id: str
    outbound_message_id: str
    assistant_text: str


class RequestScheduleApprovalInputDTO(pydantic.BaseModel):
    request_id: str | None = None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"]
    patient_location: str | None = None
    patient_preference_note: str
    hard_constraints: list[str] = pydantic.Field(default_factory=list)
    rejection_summary: str | None = None


class SubmitConsultationReasonForReviewToolInputDTO(pydantic.BaseModel):
    request_id: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_age: int | str | None = None
    consultation_reason: str | None = None
    consultation_details: str | None = None


class ConsultationReviewDecisionDTO(pydantic.BaseModel):
    decision: typing.Literal["APPROVE", "REQUEST_MORE_INFO", "REJECT"]
    professional_note: str | None = None


class ConsultationReviewDecisionResponseDTO(pydantic.BaseModel):
    status: str
    outbound_message_id: str
    assistant_text: str


class ConfirmSelectedSlotInputDTO(pydantic.BaseModel):
    request_id: str
    slot_id: str
    event_summary: str


class ConfirmSelectedSlotToolInputDTO(pydantic.BaseModel):
    request_id: str | None = None
    slot_id: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_email: str | None = None
    patient_phone: str | None = None
    patient_age: int | str | None = None
    consultation_reason: str | None = None
    patient_location: str | None = None


class ConfirmSelectedSlotResponseDTO(pydantic.BaseModel):
    status: typing.Literal["BOOKED", "SLOT_CONFLICT", "HUMAN_REQUIRED"]
    request_id: str
    selected_slot_id: str | None
    calendar_event_id: str | None
    remaining_slot_ids: list[str]


class HandoffToHumanInputDTO(pydantic.BaseModel):
    reason: str
    summary_for_professional: str


class CancelActiveSchedulingRequestInputDTO(pydantic.BaseModel):
    reason: str | None = None
