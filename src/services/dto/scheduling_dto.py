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
    audience_type: typing.Literal["ADULTS", "CHILDREN"] | None = None
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
    payment_amount_cop: int | None
    payment_method: typing.Literal["CASH", "TRANSFER"] | None
    payment_status: typing.Literal["PENDING", "PAID"]
    payment_updated_at: datetime.datetime | None
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


class SubmitConsultationReasonForReviewToolInputDTO(pydantic.BaseModel):
    request_id: str | None = None
    consultation_reason: str | None = None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None = None
    patient_location: str | None = None


class ConsultationReviewDecisionDTO(pydantic.BaseModel):
    decision: typing.Literal["REQUEST_MORE_INFO", "REJECT"]
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
    patient_full_name: str | None = None
    # Legacy compatibility fields; prefer patient_full_name.
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


class RescheduleBookedSlotInputDTO(pydantic.BaseModel):
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    event_summary: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_range(self) -> "RescheduleBookedSlotInputDTO":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be greater than start_at")
        return self


class CancelBookedSlotInputDTO(pydantic.BaseModel):
    reason: str | None = None


class PaymentReviewDecisionDTO(pydantic.BaseModel):
    decision: typing.Literal["APPROVE", "SEND_REMINDER"]
    professional_note: str | None = None


class PaymentReviewDecisionResponseDTO(pydantic.BaseModel):
    status: str
    outbound_message_id: str
    assistant_text: str


class UpdateBookedSlotPaymentInputDTO(pydantic.BaseModel):
    payment_amount_cop: int
    payment_method: typing.Literal["CASH", "TRANSFER"]
    payment_status: typing.Literal["PENDING", "PAID"]

    @pydantic.field_validator("payment_amount_cop")
    @classmethod
    def validate_payment_amount_cop(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("payment_amount_cop must be greater than zero")
        return value
