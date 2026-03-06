import typing

import pydantic


class ConversationWorkflowInputDTO(pydantic.BaseModel):
    tenant_id: str
    conversation_id: str
    whatsapp_user_id: str
    latest_user_text: str


class ConversationWorkflowResultDTO(pydantic.BaseModel):
    mode: typing.Literal["SEND_MESSAGE", "SKIP_SILENT"]
    reason: typing.Literal[
        "AI_REPLY",
        "PATIENT_CHOICE_OVERRIDE",
        "NUMERIC_SLOT_RETRY",
        "WAITING_PROFESSIONAL_OVERRIDE",
        "WAITING_PROFESSIONAL_SILENT",
    ]
    text: str | None = None
    runtime_state: str | None = None
    enabled_tool_names: list[str] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def validate_text_requirement(self) -> "ConversationWorkflowResultDTO":
        if self.mode == "SEND_MESSAGE":
            normalized_text = None
            if self.text is not None:
                normalized_text = self.text.strip()
            if normalized_text is None or normalized_text == "":
                raise ValueError("text is required when mode is SEND_MESSAGE")
            self.text = normalized_text
        return self


class SchedulingTransitionInputDTO(pydantic.BaseModel):
    action: typing.Literal[
        "SUBMIT_CONSULTATION_REASON",
        "RESOLVE_CONSULTATION_REVIEW",
        "SELECT_SLOT_FOR_CONFIRMATION",
        "CONFIRM_SLOT_AND_CREATE_EVENT",
        "CANCEL_ACTIVE_REQUEST",
        "HANDOFF_TO_HUMAN",
        "RESCHEDULE_BOOKED_SLOT",
        "CANCEL_BOOKED_SLOT",
        "UPDATE_BOOKED_PAYMENT",
        "APPROVE_PAYMENT",
    ]
    payload: object | None = None


class SchedulingTransitionResultDTO(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    action: str
    result: object
