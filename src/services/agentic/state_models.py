import typing

import pydantic


class RuntimePromptContext(pydantic.BaseModel):
    state: typing.Literal[
        "NO_ACTIVE_REQUEST",
        "AWAITING_CONSULTATION_DETAILS",
        "AWAITING_PATIENT_CHOICE",
        "AWAITING_PAYMENT_CONFIRMATION",
        "COLLECTING_CONFIRMATION_DATA",
        "AWAITING_CONSULTATION_REVIEW",
    ]
    request_id: str | None = None
    request_status: str | None = None
    professional_note: str | None = None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None = None
    patient_location: str | None = None
    patient_preference_note: str | None = None
    selected_slot_id: str | None = None
    missing_confirmation_fields: list[str] = pydantic.Field(default_factory=list)
    enabled_tool_names: list[str] = pydantic.Field(default_factory=list)


class ConversationGraphState(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    conversation_id: str
    whatsapp_user_id: str
    latest_user_text: str
    runtime_port: object

    runtime_context: RuntimePromptContext | None = None
    enabled_tool_names: list[str] = pydantic.Field(default_factory=list)
    built_prompt_preview: str | None = None
    llm_response_text: str | None = None

    terminal_mode: typing.Literal["PENDING", "SEND_MESSAGE", "SKIP_SILENT"] = "PENDING"
    terminal_reason: (
        typing.Literal[
            "AI_REPLY",
            "PATIENT_CHOICE_OVERRIDE",
            "NUMERIC_SLOT_RETRY",
            "WAITING_PROFESSIONAL_OVERRIDE",
            "WAITING_PROFESSIONAL_SILENT",
        ]
        | None
    ) = None
    terminal_text: str | None = None


class SchedulingTransitionGraphState(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    action: str
    input_payload: object | None
    runtime_port: object

    transition_result: object | None = None
    transition_output: object | None = None
    validated: bool = False
    side_effects_executed: bool = False
    persisted: bool = False
