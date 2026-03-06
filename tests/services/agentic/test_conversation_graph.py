import src.ports.agent_workflow_port as agent_workflow_port
import src.services.agentic.state_models as agentic_state_models
import src.services.agentic.workflow_engine as workflow_engine
import src.services.dto.agent_workflow_dto as agent_workflow_dto


class FakeConversationRuntime(agent_workflow_port.ConversationWorkflowRuntimePort):
    def __init__(
        self,
        patient_choice_override: str | None,
        numeric_slot_retry: str | None,
        waiting_override: str | None,
        waiting_silent: bool,
        llm_text: str,
    ) -> None:
        self._patient_choice_override = patient_choice_override
        self._numeric_slot_retry = numeric_slot_retry
        self._waiting_override = waiting_override
        self._waiting_silent = waiting_silent
        self._llm_text = llm_text
        self.llm_calls = 0

    def load_runtime_prompt_context(self) -> agentic_state_models.RuntimePromptContext:
        return agentic_state_models.RuntimePromptContext(
            state="AWAITING_CONSULTATION_REVIEW",
            enabled_tool_names=["submit_consultation_reason_for_review"],
        )

    def handle_waiting_patient_choice_override(self) -> str | None:
        return self._patient_choice_override

    def enforce_required_numeric_slot_selection(self) -> str | None:
        return self._numeric_slot_retry

    def handle_waiting_professional_override(self) -> str | None:
        return self._waiting_override

    def is_waiting_professional_state_active(self) -> bool:
        return self._waiting_silent

    def build_runtime_prompt_preview(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
    ) -> str:
        return f"preview-{runtime_context.state}"

    def generate_reply_with_tools(self) -> str:
        self.llm_calls += 1
        return self._llm_text


def test_conversation_graph_short_circuits_patient_choice_override() -> None:
    engine = workflow_engine.LangGraphAgentWorkflowEngine()
    runtime = FakeConversationRuntime(
        patient_choice_override="elige por numero",
        numeric_slot_retry=None,
        waiting_override=None,
        waiting_silent=False,
        llm_text="no-should-use",
    )

    result = engine.run_conversation_flow(
        input_dto=agent_workflow_dto.ConversationWorkflowInputDTO(
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            latest_user_text="hola",
        ),
        runtime_port=runtime,
    )

    assert result.mode == "SEND_MESSAGE"
    assert result.reason == "PATIENT_CHOICE_OVERRIDE"
    assert result.text == "elige por numero"
    assert runtime.llm_calls == 0


def test_conversation_graph_short_circuits_waiting_professional_silent() -> None:
    engine = workflow_engine.LangGraphAgentWorkflowEngine()
    runtime = FakeConversationRuntime(
        patient_choice_override=None,
        numeric_slot_retry=None,
        waiting_override=None,
        waiting_silent=True,
        llm_text="no-should-use",
    )

    result = engine.run_conversation_flow(
        input_dto=agent_workflow_dto.ConversationWorkflowInputDTO(
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            latest_user_text="hola",
        ),
        runtime_port=runtime,
    )

    assert result.mode == "SKIP_SILENT"
    assert result.reason == "WAITING_PROFESSIONAL_SILENT"
    assert result.text is None
    assert runtime.llm_calls == 0


def test_conversation_graph_runs_llm_when_no_guards_apply() -> None:
    engine = workflow_engine.LangGraphAgentWorkflowEngine()
    runtime = FakeConversationRuntime(
        patient_choice_override=None,
        numeric_slot_retry=None,
        waiting_override=None,
        waiting_silent=False,
        llm_text="respuesta final",
    )

    result = engine.run_conversation_flow(
        input_dto=agent_workflow_dto.ConversationWorkflowInputDTO(
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            latest_user_text="hola",
        ),
        runtime_port=runtime,
    )

    assert result.mode == "SEND_MESSAGE"
    assert result.reason == "AI_REPLY"
    assert result.text == "respuesta final"
    assert result.runtime_state == "AWAITING_CONSULTATION_REVIEW"
    assert result.enabled_tool_names == ["submit_consultation_reason_for_review"]
    assert runtime.llm_calls == 1
