import datetime

import pydantic


class ScheduledReminderDTO(pydantic.BaseModel):
    reminder_id: str
    source_type: str
    source_id: str
    patient_whatsapp_user_id: str
    patient_name: str
    appointment_start_at: datetime.datetime
    reminder_scheduled_for: datetime.datetime
    template_name: str
    status: str
    created_at: datetime.datetime


class ScheduledReminderListResponseDTO(pydantic.BaseModel):
    items: list[ScheduledReminderDTO]
