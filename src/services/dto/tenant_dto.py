import pydantic


class TenantProfileDTO(pydantic.BaseModel):
    tenant_id: str
    name: str
    professional_name: str | None


class UpdateTenantProfileDTO(pydantic.BaseModel):
    professional_name: str | None
