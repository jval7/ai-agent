import datetime

import pydantic


class Patient(pydantic.BaseModel):
    tenant_id: str
    whatsapp_user_id: str
    first_name: str
    last_name: str
    email: str
    age: int
    consultation_reason: str
    location: str
    phone: str
    created_at: datetime.datetime

    @pydantic.field_validator(
        "tenant_id",
        "whatsapp_user_id",
        "first_name",
        "last_name",
        "email",
        "consultation_reason",
        "location",
        "phone",
    )
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("patient text fields cannot be empty")
        return normalized_value

    @pydantic.field_validator("age")
    @classmethod
    def validate_age(cls, value: int) -> int:
        if value < 1 or value > 120:
            raise ValueError("patient age must be between 1 and 120")
        return value
