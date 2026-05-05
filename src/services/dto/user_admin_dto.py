import datetime

import pydantic

import src.services.constants as service_constants

ALLOWED_ROLES = (service_constants.ROLE_PROFESSIONAL, service_constants.ROLE_ADMIN)


def _validate_role(value: str) -> str:
    normalized_value = value.strip().lower()
    if normalized_value not in ALLOWED_ROLES:
        raise ValueError(f"role must be one of {ALLOWED_ROLES}")
    return normalized_value


class CreateProfessionalDTO(pydantic.BaseModel):
    tenant_name: str
    email: str
    password: str
    role: str = service_constants.ROLE_PROFESSIONAL

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

    @pydantic.field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return _validate_role(value)

    @pydantic.model_validator(mode="after")
    def validate_tenant_name_required_for_professional(self) -> "CreateProfessionalDTO":
        if self.role != service_constants.ROLE_ADMIN and not self.tenant_name.strip():
            raise ValueError("tenant_name cannot be empty for professional role")
        return self


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


class ProfessionalSummaryDTO(pydantic.BaseModel):
    user_id: str
    tenant_id: str
    tenant_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime.datetime


class InviteProfessionalDTO(pydantic.BaseModel):
    tenant_name: str
    email: str
    professional_name: str | None = None
    role: str = service_constants.ROLE_PROFESSIONAL

    @pydantic.field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if "@" not in normalized_value:
            raise ValueError("email must contain @")
        return normalized_value

    @pydantic.field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return _validate_role(value)

    @pydantic.model_validator(mode="after")
    def validate_tenant_name_required_for_professional(self) -> "InviteProfessionalDTO":
        if self.role != service_constants.ROLE_ADMIN and not self.tenant_name.strip():
            raise ValueError("tenant_name cannot be empty for professional role")
        return self
