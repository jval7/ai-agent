import pydantic


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


class UpdateAgentSettingsDTO(pydantic.BaseModel):
    message_debounce_delay_seconds: int

    @pydantic.field_validator("message_debounce_delay_seconds")
    @classmethod
    def validate_range(cls, value: int) -> int:
        if value < 0 or value > 30:
            raise ValueError("message_debounce_delay_seconds must be between 0 and 30")
        return value


class AgentSettingsResponseDTO(pydantic.BaseModel):
    tenant_id: str
    message_debounce_delay_seconds: int
