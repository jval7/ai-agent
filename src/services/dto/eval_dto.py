import datetime
import typing

import pydantic


class EvalCapabilityDocDTO(pydantic.BaseModel):
    id: str
    description: str
    implications: str
    category: typing.Literal["location", "cohort", "behavior"]


class EvalCapabilitiesListResponseDTO(pydantic.BaseModel):
    items: list[EvalCapabilityDocDTO]


class CapabilityVerificationDTO(pydantic.BaseModel):
    capability: str
    verified: bool
    evidence: str | None = None
    reasoning: str | None = None


class JudgeVerdictDTO(pydantic.BaseModel):
    declared_capabilities: list[str]
    verifications: list[CapabilityVerificationDTO]
    overall: typing.Literal["all_verified", "partial", "none"]
    judge_model: str
    judged_at: datetime.datetime
    error: str | None = None


class ShapeDTO(pydantic.BaseModel):
    name: str
    description: str
    required_combos: list[list[str]]
    rendered_system_prompt: str


class PersonaDTO(pydantic.BaseModel):
    id: str
    display_name: str
    capabilities: list[str]
    # Agrupador libre del eval framework. Inicialmente "psicologa" |
    # "ortodoncista" pero abierto a string para extender el pool sin tocar
    # la entity. Convencionalmente lowercase, snake_case (Fix B4).
    profile_group: str


class PromptVersionDTO(pydantic.BaseModel):
    id: str
    label: str
    active: bool


class EvalRunListItemDTO(pydantic.BaseModel):
    """Item resumido para el listado."""

    run_doc_id: str
    run_id: str
    shape_name: str
    started_at: datetime.datetime
    finished_at: datetime.datetime | None
    total_personas: int
    ok: int
    fail: int
    skipped: bool


class EvalRunConversationMessageDTO(pydantic.BaseModel):
    direction: typing.Literal["INBOUND", "OUTBOUND"]
    content: str
    timestamp: datetime.datetime


class EvalRunConversationSnapshotDTO(pydantic.BaseModel):
    persona_id: str
    combos_satisfied: list[list[str]]
    status: typing.Literal["ok", "fail", "skipped"]
    elapsed_seconds: float
    conversation_id: str | None = None
    scheduling_request_id: str | None = None
    final_status: str | None = None
    transcript: list[EvalRunConversationMessageDTO] = []
    error: str | None = None
    judge_verdict: JudgeVerdictDTO | None = None


class EvalRunDetailDTO(pydantic.BaseModel):
    """Detalle completo de un run, incluye conversaciones con transcripts."""

    run_doc_id: str
    run_id: str
    shape_name: str
    prompt_version_id: str | None
    started_at: datetime.datetime
    finished_at: datetime.datetime | None
    total_personas: int
    ok: int
    fail: int
    skipped: bool
    uncovered_combos: list[list[str]] = []
    eval_tenant_id: str | None
    conversations: list[EvalRunConversationSnapshotDTO]


class ShapesListResponseDTO(pydantic.BaseModel):
    items: list[ShapeDTO]


class PersonasListResponseDTO(pydantic.BaseModel):
    items: list[PersonaDTO]


class PromptVersionsListResponseDTO(pydantic.BaseModel):
    items: list[PromptVersionDTO]


class EvalRunsListResponseDTO(pydantic.BaseModel):
    items: list[EvalRunListItemDTO]
