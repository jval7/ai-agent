import typing

import pydantic

import src.domain.official_reminder_templates as official_reminder_templates


class TemplateComponentDTO(pydantic.BaseModel):
    type: str  # HEADER, BODY, FOOTER
    text: str
    example_values: list[str] = pydantic.Field(default_factory=list)


class CreateTemplateRequestDTO(pydantic.BaseModel):
    name: str
    category: str  # MARKETING, UTILITY, AUTHENTICATION
    language: str  # es, en, pt_BR
    components: list[TemplateComponentDTO]


class TemplateDTO(pydantic.BaseModel):
    id: str
    name: str
    category: str
    language: str
    status: str  # APPROVED, PENDING, REJECTED, DISABLED
    components: list[TemplateComponentDTO]


class TemplateListDTO(pydantic.BaseModel):
    templates: list[TemplateDTO]


OfficialTemplateMetaStatus = typing.Literal[
    "NOT_CREATED", "PENDING", "APPROVED", "REJECTED", "DISABLED"
]


class OfficialTemplateStatusDTO(pydantic.BaseModel):
    kind: official_reminder_templates.OfficialReminderKind
    name: str
    meta_status: OfficialTemplateMetaStatus
    rejection_reason: str | None = None


class OfficialTemplateListDTO(pydantic.BaseModel):
    items: list[OfficialTemplateStatusDTO]
