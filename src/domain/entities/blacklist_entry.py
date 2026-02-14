import datetime

import pydantic


class BlacklistEntry(pydantic.BaseModel):
    tenant_id: str
    whatsapp_user_id: str
    created_at: datetime.datetime

    @pydantic.field_validator("whatsapp_user_id")
    @classmethod
    def validate_whatsapp_user_id(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("whatsapp_user_id cannot be empty")
        return normalized_value
