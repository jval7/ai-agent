import typing

import pydantic

# ---------------------------------------------------------------------------
# Professional Profile DTOs (structured form fields)
# ---------------------------------------------------------------------------


class AssistantIdentityDTO(pydantic.BaseModel):
    assistant_name: str | None = None
    professional_title: str | None = None
    professional_address_term: str | None = None
    main_city: str | None = None
    tone: str | None = None
    languages: list[str] = []


class ScheduleBlockDTO(pydantic.BaseModel):
    weekday_from: typing.Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    weekday_to: typing.Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] | None = None
    start_time: str
    end_time: str


class TariffPriceDTO(pydantic.BaseModel):
    currency: str
    amount: float


class TariffOptionDTO(pydantic.BaseModel):
    label: str
    description: str | None = None
    prices: list[TariffPriceDTO] = []


class ServiceOfferingDTO(pydantic.BaseModel):
    name: str | None = None
    description: str | None = None
    modalities: list[typing.Literal["PRESENCIAL", "VIRTUAL"]] = []
    tariffs: list[TariffOptionDTO] = []


class PaymentMethodDTO(pydantic.BaseModel):
    currency: str
    method_name: str
    holder: str | None = None
    instructions: str | None = None
    applies_when: str | None = None


class ProfessionalContextDTO(pydantic.BaseModel):
    approach: str | None = None
    common_topics: list[str] = []
    services_not_offered: list[str] = []
    coverage_notes: str | None = None


class ProfessionalProfileResponseDTO(pydantic.BaseModel):
    tenant_id: str
    identity: AssistantIdentityDTO | None = None
    professional_context: ProfessionalContextDTO | None = None
    services: list[ServiceOfferingDTO] = []
    presencial_schedule: list[ScheduleBlockDTO] = []
    virtual_schedule: list[ScheduleBlockDTO] = []
    payment_methods: list[PaymentMethodDTO] = []


class UpdateProfessionalProfileDTO(pydantic.BaseModel):
    identity: AssistantIdentityDTO | None = None
    professional_context: ProfessionalContextDTO | None = None
    services: list[ServiceOfferingDTO] = []
    presencial_schedule: list[ScheduleBlockDTO] = []
    virtual_schedule: list[ScheduleBlockDTO] = []
    payment_methods: list[PaymentMethodDTO] = []


# ---------------------------------------------------------------------------
# Legacy system-prompt and settings DTOs
# ---------------------------------------------------------------------------


PaymentTimingLiteral = typing.Literal["BEFORE_SESSION", "IN_PERSON"]


class UpdateSystemPromptDTO(pydantic.BaseModel):
    system_prompt: str

    @pydantic.field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("system_prompt cannot be empty")
        return normalized_value


class SystemPromptResponseDTO(pydantic.BaseModel):
    tenant_id: str
    system_prompt: str


class OfficeLocationDTO(pydantic.BaseModel):
    address: str
    arrival_instructions: str | None = None


class UpdateAgentSettingsDTO(pydantic.BaseModel):
    message_debounce_delay_seconds: int
    appointment_reminder_enabled: bool = False
    appointment_reminder_days_before: int | None = None
    appointment_reminder_attendance_template_name: str | None = None
    appointment_reminder_payment_template_name: str | None = None
    payment_details_text: str | None = None
    office_location: OfficeLocationDTO | None = None
    payment_timing: PaymentTimingLiteral = "BEFORE_SESSION"

    @pydantic.field_validator("message_debounce_delay_seconds")
    @classmethod
    def validate_debounce_range(cls, value: int) -> int:
        if value < 0 or value > 30:
            raise ValueError("message_debounce_delay_seconds must be between 0 and 30")
        return value

    @pydantic.field_validator("appointment_reminder_days_before")
    @classmethod
    def validate_days_before(cls, value: int | None) -> int | None:
        if value is not None and (value < 1 or value > 7):
            raise ValueError("appointment_reminder_days_before must be between 1 and 7")
        return value

    @pydantic.model_validator(mode="after")
    def validate_reminder_fields_required_when_enabled(self) -> typing.Self:
        if self.appointment_reminder_enabled:
            if self.appointment_reminder_days_before is None:
                raise ValueError(
                    "appointment_reminder_days_before is required when appointment_reminder_enabled is True"
                )
            if self.appointment_reminder_attendance_template_name is None:
                raise ValueError(
                    "appointment_reminder_attendance_template_name is required when appointment_reminder_enabled is True"
                )
        return self


class AgentSettingsResponseDTO(pydantic.BaseModel):
    tenant_id: str
    message_debounce_delay_seconds: int
    appointment_reminder_enabled: bool
    appointment_reminder_days_before: int | None
    appointment_reminder_attendance_template_name: str | None
    appointment_reminder_payment_template_name: str | None
    payment_details_text: str | None
    office_location: OfficeLocationDTO | None = None
    payment_timing: PaymentTimingLiteral = "BEFORE_SESSION"
