import datetime
import re
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


_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

_WEEKDAY_LITERAL = typing.Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class AssistantIdentity(pydantic.BaseModel):
    assistant_name: str | None = None
    professional_title: str | None = None
    professional_address_term: str | None = None
    main_city: str | None = None
    tone: str | None = None
    languages: list[str] = []


class ScheduleBlock(pydantic.BaseModel):
    weekday_from: _WEEKDAY_LITERAL
    weekday_to: _WEEKDAY_LITERAL | None = None
    start_time: str  # "HH:MM" 24h
    end_time: str

    @pydantic.field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str) -> str:
        if not _TIME_RE.match(value):
            raise ValueError("time must be in HH:MM format")
        return value


class TariffOption(pydantic.BaseModel):
    label: str
    amount: float
    currency: str  # 3 chars, e.g. "COP", "USD"
    discount_percent: float | None = None

    @pydantic.field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("currency must be a 3-character code")
        return normalized


class ServiceOffering(pydantic.BaseModel):
    name: str | None = None
    description: str | None = None
    audience: str | None = None
    modalities: list[typing.Literal["PRESENCIAL", "VIRTUAL"]] = []
    tariffs_local: list[TariffOption] = []
    tariffs_foreign: list[TariffOption] = []


class PaymentMethod(pydantic.BaseModel):
    currency: str  # "COP", "USD"
    method_name: str  # "Nequi", "Zelle"
    holder: str | None = None
    instructions: str | None = None
    applies_when: str | None = None

    @pydantic.field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("currency must be a 3-character code")
        return normalized


class ProfessionalContext(pydantic.BaseModel):
    approach: str | None = None
    common_topics: list[str] = []
    services_not_offered: list[str] = []
    coverage_notes: str | None = None


class AgentProfile(pydantic.BaseModel):
    tenant_id: str
    system_prompt: str = ""
    message_debounce_delay_seconds: int = 0
    appointment_reminder_enabled: bool = False
    appointment_reminder_days_before: int | None = None
    appointment_reminder_attendance_template_name: str | None = None
    appointment_reminder_payment_template_name: str | None = None
    payment_details_text: str | None = None
    office_location: OfficeLocation | None = None
    identity: AssistantIdentity | None = None
    professional_context: ProfessionalContext | None = None
    services: list[ServiceOffering] = []
    presencial_schedule: list[ScheduleBlock] = []
    virtual_schedule: list[ScheduleBlock] = []
    payment_methods: list[PaymentMethod] = []
    payment_timing: typing.Literal["BEFORE_SESSION", "IN_PERSON"] = "BEFORE_SESSION"
    updated_at: datetime.datetime

    @pydantic.field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        # Accept empty string or None-coerced-to-string: formulario todavía sin llenar
        return value.strip() if value else ""

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
