import pydantic


class EmbeddedSignupSessionResponseDTO(pydantic.BaseModel):
    state: str
    connect_url: str


class EmbeddedSignupCompleteDTO(pydantic.BaseModel):
    code: str
    state: str


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
