import datetime
import typing

import pydantic


class TagDTO(pydantic.BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    color: str
    tag_type: typing.Literal["SYSTEM", "CUSTOM"]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CreateTagDTO(pydantic.BaseModel):
    name: str
    color: str


class UpdateTagDTO(pydantic.BaseModel):
    name: str | None = None
    color: str | None = None


class TagListResponseDTO(pydantic.BaseModel):
    items: list[TagDTO]
