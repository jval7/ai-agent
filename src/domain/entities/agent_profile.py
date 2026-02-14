import datetime

import pydantic


class AgentProfile(pydantic.BaseModel):
    tenant_id: str
    system_prompt: str
    updated_at: datetime.datetime

    @pydantic.field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("system_prompt cannot be empty")
        return normalized_value
