import pydantic


class CreateProfessionalDTO(pydantic.BaseModel):
    tenant_name: str
    email: str
    password: str

    @pydantic.field_validator("tenant_name")
    @classmethod
    def validate_tenant_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("tenant_name cannot be empty")
        return normalized_value

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("email must contain @")
        return normalized_value

    @pydantic.field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must have at least 8 characters")
        return value


class ResetPasswordDTO(pydantic.BaseModel):
    email: str
    new_password: str

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("email must contain @")
        return normalized_value

    @pydantic.field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("new_password must have at least 8 characters")
        return value


class DeleteProfessionalDTO(pydantic.BaseModel):
    email: str

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("email must contain @")
        return normalized_value
