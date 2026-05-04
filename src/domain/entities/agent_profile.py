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


class AssistantIdentity(pydantic.BaseModel):
    assistant_name: str | None = None
    professional_title: str | None = None  # "Doc.", "Psic.", "Dra." — prefix
    professional_name: str | None = None  # "Ana Rodriguez" — full name
    professional_address_term: str | None = None  # "la Doc" — third-person ref
    main_city: str | None = None
    timezone: str | None = None  # IANA timezone, e.g. "America/Bogota"
    tone: str | None = None
    languages: list[str] = []


class TariffPrice(pydantic.BaseModel):
    """A single price point inside a tariff (currency + amount)."""

    currency: str  # 3 chars, e.g. "COP", "USD"
    amount: float

    @pydantic.field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("currency must be a 3-character code")
        return normalized


class TariffOption(pydantic.BaseModel):
    """A tariff line with one or more price points (one per currency)."""

    label: str
    description: str | None = None
    prices: list[TariffPrice] = []

    @pydantic.model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: typing.Any) -> typing.Any:
        """Backwards-compat: previous Firestore docs may have:
          - `discount_percent` (number): converted to `description` text.
          - top-level `currency` + `amount`: wrapped into `prices: [{...}]`.
        Both transforms run only when the new field is absent so an explicit
        new-shape payload always wins.
        """
        if not isinstance(data, dict):
            return data
        # discount_percent → description
        legacy_discount = data.pop("discount_percent", None)
        if "description" not in data and legacy_discount is not None:
            try:
                pct = float(legacy_discount)
            except (TypeError, ValueError):
                pct = 0.0
            if pct > 0:
                pct_text = f"{int(pct)}" if pct == int(pct) else f"{pct:.2f}"
                data["description"] = f"{pct_text}% descuento"
        # top-level currency+amount → prices list
        legacy_currency = data.pop("currency", None)
        legacy_amount = data.pop("amount", None)
        if "prices" not in data and legacy_currency is not None and legacy_amount is not None:
            data["prices"] = [{"currency": legacy_currency, "amount": legacy_amount}]
        return data


class ServiceOffering(pydantic.BaseModel):
    name: str | None = None
    description: str | None = None
    modalities: list[typing.Literal["PRESENCIAL", "VIRTUAL"]] = []
    # Which patient cohort this service applies to. Default both so legacy
    # services without the field stay fully visible. The bot uses this to
    # decide which services to surface based on whether the patient is
    # already registered (RETURNING) or completely new (NEW).
    target_patients: list[typing.Literal["NEW", "RETURNING"]] = ["NEW", "RETURNING"]
    tariffs: list[TariffOption] = []

    @pydantic.model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: typing.Any) -> typing.Any:
        """Backwards-compat: pre-existing Firestore docs may have:
          - `audience` (str): dropped silently.
          - `tariffs_local` + `tariffs_foreign`: merged into a single `tariffs`
            list when `tariffs` is not already present.
        Once a tenant saves through the new form, those keys disappear.
        """
        if not isinstance(data, dict):
            return data
        # Drop legacy `audience` field.
        data.pop("audience", None)
        # Merge legacy split tariffs into the unified list.
        legacy_local = data.pop("tariffs_local", None)
        legacy_foreign = data.pop("tariffs_foreign", None)
        if "tariffs" not in data:
            merged: list[typing.Any] = []
            if isinstance(legacy_local, list):
                merged.extend(legacy_local)
            if isinstance(legacy_foreign, list):
                merged.extend(legacy_foreign)
            if merged:
                data["tariffs"] = merged
        return data


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
    assistant_enabled: bool = True
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
    payment_methods: list[PaymentMethod] = []
    payment_timing: typing.Literal["BEFORE_SESSION", "AFTER_SESSION"] = "BEFORE_SESSION"
    updated_at: datetime.datetime

    @pydantic.model_validator(mode="before")
    @classmethod
    def _migrate_legacy_payment_timing(cls, data: typing.Any) -> typing.Any:
        """Backwards-compat: pre-existing Firestore docs may have
        `payment_timing: "IN_PERSON"`. The option was renamed to
        `AFTER_SESSION` because virtual sessions can also be charged after.
        """
        if isinstance(data, dict) and data.get("payment_timing") == "IN_PERSON":
            data["payment_timing"] = "AFTER_SESSION"
        return data

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
