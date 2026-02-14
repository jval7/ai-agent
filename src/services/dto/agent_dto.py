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
