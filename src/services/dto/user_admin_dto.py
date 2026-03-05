import pydantic


class BootstrapMasterDTO(pydantic.BaseModel):
    tenant_name: str
    master_email: str
    master_password: str

    @pydantic.field_validator("tenant_name")
    @classmethod
    def validate_tenant_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("tenant_name cannot be empty")
        return normalized_value

    @pydantic.field_validator("master_email")
    @classmethod
    def validate_master_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("master_email must contain @")
        return normalized_value

    @pydantic.field_validator("master_password")
    @classmethod
    def validate_master_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("master_password must have at least 8 characters")
        return value


class CreateUserByMasterDTO(pydantic.BaseModel):
    master_email: str
    master_password: str
    email: str
    password: str

    @pydantic.field_validator("master_email")
    @classmethod
    def validate_master_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("master_email must contain @")
        return normalized_value

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("email must contain @")
        return normalized_value

    @pydantic.field_validator("master_password")
    @classmethod
    def validate_master_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("master_password must have at least 8 characters")
        return value

    @pydantic.field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must have at least 8 characters")
        return value


class DeleteUserByMasterDTO(pydantic.BaseModel):
    master_email: str
    master_password: str
    email: str

    @pydantic.field_validator("master_email")
    @classmethod
    def validate_master_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("master_email must contain @")
        return normalized_value

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("email must contain @")
        return normalized_value

    @pydantic.field_validator("master_password")
    @classmethod
    def validate_master_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("master_password must have at least 8 characters")
        return value
