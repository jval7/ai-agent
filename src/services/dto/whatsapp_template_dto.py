import pydantic


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
