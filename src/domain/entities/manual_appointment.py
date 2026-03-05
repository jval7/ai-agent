import datetime
import typing

import pydantic


class ManualAppointment(pydantic.BaseModel):
    id: str
    tenant_id: str
    patient_whatsapp_user_id: str
    status: typing.Literal["SCHEDULED", "CANCELLED"]
    calendar_event_id: str | None
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    summary: str
    payment_amount_cop: int | None = None
    payment_method: typing.Literal["CASH", "TRANSFER"] | None = None
    payment_status: typing.Literal["PENDING", "PAID"] = "PENDING"
    payment_updated_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    cancelled_at: datetime.datetime | None = None

    @pydantic.model_validator(mode="after")
    def validate_time_range(self) -> "ManualAppointment":
        if self.end_at <= self.start_at:
            raise ValueError("appointment end_at must be greater than start_at")
        return self

    @pydantic.field_validator("id", "tenant_id", "patient_whatsapp_user_id", "timezone", "summary")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("manual appointment text fields cannot be empty")
        return normalized_value

    @pydantic.field_validator("payment_amount_cop")
    @classmethod
    def validate_payment_amount_cop(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("payment_amount_cop must be greater than zero")
        return value
