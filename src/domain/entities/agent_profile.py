import datetime

import pydantic


class AgentProfile(pydantic.BaseModel):
    tenant_id: str
    system_prompt: str
    message_debounce_delay_seconds: int = 0
    updated_at: datetime.datetime

    @pydantic.field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("system_prompt cannot be empty")
        return normalized_value

    @pydantic.field_validator("message_debounce_delay_seconds")
    @classmethod
    def validate_debounce_delay(cls, value: int) -> int:
        if value < 0 or value > 30:
            raise ValueError("message_debounce_delay_seconds must be between 0 and 30")
        return value
