import datetime
import typing

import pydantic


class OfficeLocation(pydantic.BaseModel):
    address: str
    arrival_instructions: str | None = None

    @pydantic.field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("office_location.address cannot be empty")
        return normalized


class AgentProfile(pydantic.BaseModel):
    tenant_id: str
    system_prompt: str
    message_debounce_delay_seconds: int = 0
    appointment_reminder_enabled: bool = False
    appointment_reminder_days_before: int | None = None
    appointment_reminder_attendance_template_name: str | None = None
    appointment_reminder_payment_template_name: str | None = None
    reminder_billing_test_phone_number: str | None = None
    payment_details_text: str | None = None
    office_location: OfficeLocation | None = None
    updated_at: datetime.datetime

    @pydantic.field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("system_prompt cannot be empty")
        return normalized_value

    @pydantic.field_validator("message_debounce_delay_seconds")
    @classmethod
    def validate_debounce_delay(cls, value: int) -> int:
        if value < 0 or value > 30:
            raise ValueError("message_debounce_delay_seconds must be between 0 and 30")
        return value

    @pydantic.field_validator("appointment_reminder_days_before")
    @classmethod
    def validate_reminder_days_before(cls, value: int | None) -> int | None:
        if value is not None and (value < 1 or value > 7):
            raise ValueError("appointment_reminder_days_before must be between 1 and 7")
        return value

    @pydantic.model_validator(mode="after")
    def validate_reminder_config(self) -> typing.Self:
        if self.appointment_reminder_enabled:
            if self.appointment_reminder_days_before is None:
                raise ValueError(
                    "appointment_reminder_days_before is required when reminder is enabled"
                )
            if self.appointment_reminder_attendance_template_name is None:
                raise ValueError(
                    "appointment_reminder_attendance_template_name is required when reminder is enabled"
                )
        return self
