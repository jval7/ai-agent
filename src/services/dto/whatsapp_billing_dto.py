import re

import pydantic

E164_PATTERN = re.compile(r"^\+\d{8,15}$")


class BillingPreflightRequestDTO(pydantic.BaseModel):
    recipient_phone_number: str

    @pydantic.field_validator("recipient_phone_number")
    @classmethod
    def validate_e164(cls, value: str) -> str:
        normalized = value.strip()
        if not E164_PATTERN.match(normalized):
            raise ValueError("recipient_phone_number must be in E.164 format (e.g. +573001234567)")
        return normalized


class BillingPreflightResponseDTO(pydantic.BaseModel):
    ok: bool
    recipient_phone_number: str
