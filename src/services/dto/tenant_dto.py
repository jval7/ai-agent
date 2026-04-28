import pydantic

_VALID_SESSION_DURATIONS: frozenset[int] = frozenset({15, 30, 45, 60, 90, 120})


class TenantProfileDTO(pydantic.BaseModel):
    tenant_id: str
    name: str
    professional_name: str | None
    session_duration_minutes: int


class UpdateTenantProfileDTO(pydantic.BaseModel):
    professional_name: str | None
    session_duration_minutes: int | None = None
