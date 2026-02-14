import pydantic


class MemoryResetResponseDTO(pydantic.BaseModel):
    status: str
