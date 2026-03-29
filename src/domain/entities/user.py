import datetime

import pydantic


class User(pydantic.BaseModel):
    id: str
    tenant_id: str
    email: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime.datetime

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must contain @")
        return value.lower()
