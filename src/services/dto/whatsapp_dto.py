import pydantic


class EmbeddedSignupSessionRequestDTO(pydantic.BaseModel):
    registration_pin: str | None = None


class EmbeddedSignupSessionResponseDTO(pydantic.BaseModel):
    state: str
    connect_url: str
    app_id: str
    config_id: str


class EmbeddedSignupCompleteDTO(pydantic.BaseModel):
    code: str | None = None
    state: str
    registration_pin: str | None = None
    origin_url: str | None = None
    access_token: str | None = None


class EmbeddedSignupCredentialsDTO(pydantic.BaseModel):
    phone_number_id: str
    business_account_id: str
    access_token: str


class WhatsappConnectionStatusDTO(pydantic.BaseModel):
    tenant_id: str
    status: str
    phone_number_id: str | None
    business_account_id: str | None


class DevVerifyTokenDTO(pydantic.BaseModel):
    verify_token: str
