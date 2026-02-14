import pydantic


class RegisterUserDTO(pydantic.BaseModel):
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

    @pydantic.field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must have at least 8 characters")
        return value


class LoginDTO(pydantic.BaseModel):
    email: str
    password: str


class RefreshTokenDTO(pydantic.BaseModel):
    refresh_token: str


class LogoutDTO(pydantic.BaseModel):
    refresh_token: str


class AuthTokensDTO(pydantic.BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class TokenClaimsDTO(pydantic.BaseModel):
    sub: str
    tenant_id: str
    role: str
    exp: int
    jti: str
    token_kind: str
