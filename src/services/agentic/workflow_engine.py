import typing

import src.ports.agent_workflow_port as agent_workflow_port
import src.services.agentic.graphs.conversation_graph as conversation_graph
import src.services.agentic.graphs.scheduling_transition_graph as scheduling_transition_graph
import src.services.agentic.state_models as agentic_state_models
import src.services.dto.agent_workflow_dto as agent_workflow_dto


class LangGraphAgentWorkflowEngine(agent_workflow_port.AgentWorkflowPort):
    def __init__(self) -> None:
        self._conversation_graph = conversation_graph.ConversationGraph()
        self._scheduling_transition_graph = scheduling_transition_graph.SchedulingTransitionGraph()

    def run_conversation_flow(
        self,
        input_dto: agent_workflow_dto.ConversationWorkflowInputDTO,
        runtime_port: agent_workflow_port.ConversationWorkflowRuntimePort,
    ) -> agent_workflow_dto.ConversationWorkflowResultDTO:
        initial_state = agentic_state_models.ConversationGraphState(
            tenant_id=input_dto.tenant_id,
            conversation_id=input_dto.conversation_id,
            whatsapp_user_id=input_dto.whatsapp_user_id,
            latest_user_text=input_dto.latest_user_text,
            runtime_port=runtime_port,
        )
        final_state = self._conversation_graph.run(initial_state)

        if final_state.terminal_mode == "SEND_MESSAGE":
            return agent_workflow_dto.ConversationWorkflowResultDTO(
                mode="SEND_MESSAGE",
                reason=self._resolve_terminal_reason(final_state),
                text=final_state.terminal_text,
                runtime_state=self._resolve_runtime_state(final_state),
                enabled_tool_names=list(final_state.enabled_tool_names),
            )

        return agent_workflow_dto.ConversationWorkflowResultDTO(
            mode="SKIP_SILENT",
            reason=self._resolve_terminal_reason(final_state),
            text=None,
            runtime_state=self._resolve_runtime_state(final_state),
            enabled_tool_names=list(final_state.enabled_tool_names),
        )

    def run_scheduling_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        runtime_port: agent_workflow_port.SchedulingTransitionRuntimePort,
    ) -> agent_workflow_dto.SchedulingTransitionResultDTO:
        initial_state = agentic_state_models.SchedulingTransitionGraphState(
            action=input_dto.action,
            input_payload=input_dto.payload,
            runtime_port=runtime_port,
        )
        final_state = self._scheduling_transition_graph.run(initial_state)
        return agent_workflow_dto.SchedulingTransitionResultDTO(
            action=input_dto.action,
            result=final_state.transition_output,
        )

    def _resolve_terminal_reason(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> typing.Literal[
        "AI_REPLY",
        "PATIENT_CHOICE_OVERRIDE",
        "NUMERIC_SLOT_RETRY",
        "WAITING_PROFESSIONAL_OVERRIDE",
        "WAITING_PROFESSIONAL_SILENT",
    ]:
        if state.terminal_reason is None:
            if state.terminal_mode == "SEND_MESSAGE":
                return "AI_REPLY"
            return "WAITING_PROFESSIONAL_SILENT"
        return state.terminal_reason

    def _resolve_runtime_state(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> str | None:
        if state.runtime_context is None:
            return None
        return state.runtime_context.state
