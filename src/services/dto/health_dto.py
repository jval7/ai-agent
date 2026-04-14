import pydantic


class DependencyStatusDTO(pydantic.BaseModel):
    name: str
    status: str
    latency_ms: int
    message: str | None = None


class ReadinessResponseDTO(pydantic.BaseModel):
    status: str
    checks: list[DependencyStatusDTO]
