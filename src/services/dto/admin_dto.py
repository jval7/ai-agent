import datetime

import pydantic


class TenantSummaryDTO(pydantic.BaseModel):
    tenant_id: str
    tenant_name: str
    professional_name: str | None
    patient_count: int
    conversation_count: int
    active_conversations_today: int
    manual_appointment_count_upcoming: int
    pending_reminder_count: int
    total_revenue_cop_this_month: int
    last_activity_at: datetime.datetime | None
    owner_email: str | None
    owner_is_active: bool


class GlobalMetricsDTO(pydantic.BaseModel):
    tenants_count: int
    tenants_active: int
    total_patients: int
    total_conversations: int
    total_manual_appointments_upcoming: int
    total_pending_reminders: int
    control_mode_distribution: dict[str, int]
    top_tenants_by_conversations: list[TenantSummaryDTO]
