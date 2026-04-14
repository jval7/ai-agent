import datetime
import typing

import pydantic


class ScheduledReminder(pydantic.BaseModel):
    id: str
    tenant_id: str
    source_type: typing.Literal["SCHEDULING_REQUEST", "MANUAL_APPOINTMENT"]
    source_id: str
    patient_whatsapp_user_id: str
    patient_name: str
    appointment_start_at: datetime.datetime
    reminder_scheduled_for: datetime.datetime
    template_name: str
    template_language: str
    status: typing.Literal["PENDING", "SENT", "FAILED", "CANCELLED"] = "PENDING"
    cloud_task_name: str | None = None
    sent_at: datetime.datetime | None = None
    failure_reason: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @pydantic.field_validator(
        "id", "tenant_id", "source_id", "patient_whatsapp_user_id", "template_name"
    )
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("field cannot be empty")
        return normalized_value
