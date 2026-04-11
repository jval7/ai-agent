import datetime
import typing

import pydantic


class Tag(pydantic.BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    color: str
    tag_type: typing.Literal["SYSTEM", "CUSTOM"]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @pydantic.field_validator("id", "tenant_id", "slug")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("tag identifier fields cannot be empty")
        return normalized_value

    @pydantic.field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("tag name cannot be empty")
        if len(normalized_value) > 60:
            raise ValueError("tag name cannot exceed 60 characters")
        return normalized_value

    @pydantic.field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value.startswith("#"):
            raise ValueError("tag color must start with '#'")
        hex_part = normalized_value[1:]
        if len(hex_part) not in (3, 6):
            raise ValueError("tag color must be 3 or 6 hex characters")
        try:
            int(hex_part, 16)
        except ValueError as error:
            raise ValueError("tag color must be a valid hex value") from error
        return normalized_value
