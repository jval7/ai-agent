import datetime
import typing

import pydantic


class ManualAppointmentDTO(pydantic.BaseModel):
    appointment_id: str
    tenant_id: str
    patient_whatsapp_user_id: str
    status: typing.Literal["SCHEDULED", "CANCELLED"]
    calendar_event_id: str | None
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    summary: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    cancelled_at: datetime.datetime | None


class ManualAppointmentListResponseDTO(pydantic.BaseModel):
    items: list[ManualAppointmentDTO]


class CreateManualAppointmentDTO(pydantic.BaseModel):
    patient_whatsapp_user_id: str
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    summary: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_range(self) -> "CreateManualAppointmentDTO":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be greater than start_at")
        return self

    @pydantic.field_validator("patient_whatsapp_user_id", "timezone")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("manual appointment required text cannot be empty")
        return normalized_value


class RescheduleManualAppointmentDTO(pydantic.BaseModel):
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    summary: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_range(self) -> "RescheduleManualAppointmentDTO":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be greater than start_at")
        return self

    @pydantic.field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("timezone cannot be empty")
        return normalized_value


class CancelManualAppointmentDTO(pydantic.BaseModel):
    reason: str | None = None
