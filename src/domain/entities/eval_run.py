import datetime
import typing

import pydantic


class EvalRunConversationMessage(pydantic.BaseModel):
    direction: typing.Literal["INBOUND", "OUTBOUND"]
    content: str
    timestamp: datetime.datetime


class EvalRunConversationSnapshot(pydantic.BaseModel):
    persona_id: str
    combos_satisfied: list[list[str]]
    status: typing.Literal["ok", "fail", "skipped"]
    elapsed_seconds: float
    conversation_id: str | None = None
    scheduling_request_id: str | None = None
    final_status: str | None = None
    transcript: list[EvalRunConversationMessage] = []
    error: str | None = None


class EvalRun(pydantic.BaseModel):
    run_id: str
    shape_name: str
    prompt_version_id: str | None = None
    started_at: datetime.datetime
    finished_at: datetime.datetime | None = None
    total_personas: int
    ok: int
    fail: int
    skipped: bool
    uncovered_combos: list[list[str]] = []
    eval_tenant_id: str | None = None
