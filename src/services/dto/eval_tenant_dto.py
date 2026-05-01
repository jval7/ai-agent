import pydantic


class CreateEvalTenantRequestDTO(pydantic.BaseModel):
    run_id: str
    shape_name: str


class EvalTenantCreatedDTO(pydantic.BaseModel):
    tenant_id: str
    email: str
    password: str
    phone_number_id: str
    access_token: str
    refresh_token: str
