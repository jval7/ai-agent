import typing

import langgraph.graph as langgraph_graph

import src.ports.agent_workflow_port as agent_workflow_port
import src.services.agentic.state_models as agentic_state_models


class ConversationGraph:
    def __init__(self) -> None:
        state_graph = langgraph_graph.StateGraph(agentic_state_models.ConversationGraphState)
        state_graph.add_node("load_runtime_context", self._load_runtime_context)
        state_graph.add_node(
            "guard_waiting_patient_choice_override",
            self._guard_waiting_patient_choice_override,
        )
        state_graph.add_node(
            "guard_required_numeric_slot_selection",
            self._guard_required_numeric_slot_selection,
        )
        state_graph.add_node(
            "guard_waiting_professional_override",
            self._guard_waiting_professional_override,
        )
        state_graph.add_node(
            "guard_waiting_professional_silent",
            self._guard_waiting_professional_silent,
        )
        state_graph.add_node("build_prompt_context", self._build_prompt_context)
        state_graph.add_node("call_llm", self._call_llm)
        state_graph.add_node("execute_tools", self._execute_tools)
        state_graph.add_node("decide_terminal_output", self._decide_terminal_output)

        state_graph.add_edge(langgraph_graph.START, "load_runtime_context")
        state_graph.add_edge("load_runtime_context", "guard_waiting_patient_choice_override")
        state_graph.add_conditional_edges(
            "guard_waiting_patient_choice_override",
            self._route_on_terminal,
            {
                "continue": "guard_required_numeric_slot_selection",
                "stop": langgraph_graph.END,
            },
        )
        state_graph.add_conditional_edges(
            "guard_required_numeric_slot_selection",
            self._route_on_terminal,
            {
                "continue": "guard_waiting_professional_override",
                "stop": langgraph_graph.END,
            },
        )
        state_graph.add_conditional_edges(
            "guard_waiting_professional_override",
            self._route_on_terminal,
            {
                "continue": "guard_waiting_professional_silent",
                "stop": langgraph_graph.END,
            },
        )
        state_graph.add_conditional_edges(
            "guard_waiting_professional_silent",
            self._route_on_terminal,
            {
                "continue": "build_prompt_context",
                "stop": langgraph_graph.END,
            },
        )
        state_graph.add_edge("build_prompt_context", "call_llm")
        state_graph.add_edge("call_llm", "execute_tools")
        state_graph.add_edge("execute_tools", "decide_terminal_output")
        state_graph.add_edge("decide_terminal_output", langgraph_graph.END)
        self._graph = state_graph.compile()

    def run(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> agentic_state_models.ConversationGraphState:
        output = typing.cast(typing.Any, self._graph).invoke(state.model_dump(mode="python"))
        return agentic_state_models.ConversationGraphState.model_validate(output)

    def _load_runtime_context(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        runtime_context = runtime_port.load_runtime_prompt_context()
        return {
            "runtime_context": runtime_context,
            "enabled_tool_names": runtime_context.enabled_tool_names,
        }

    def _guard_waiting_patient_choice_override(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        guard_text = runtime_port.handle_waiting_patient_choice_override()
        if guard_text is None:
            return {}
        return {
            "terminal_mode": "SEND_MESSAGE",
            "terminal_reason": "PATIENT_CHOICE_OVERRIDE",
            "terminal_text": guard_text,
        }

    def _guard_required_numeric_slot_selection(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        guard_text = runtime_port.enforce_required_numeric_slot_selection()
        if guard_text is None:
            return {}
        return {
            "terminal_mode": "SEND_MESSAGE",
            "terminal_reason": "NUMERIC_SLOT_RETRY",
            "terminal_text": guard_text,
        }

    def _guard_waiting_professional_override(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        guard_text = runtime_port.handle_waiting_professional_override()
        if guard_text is None:
            return {}
        return {
            "terminal_mode": "SEND_MESSAGE",
            "terminal_reason": "WAITING_PROFESSIONAL_OVERRIDE",
            "terminal_text": guard_text,
        }

    def _guard_waiting_professional_silent(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        if not runtime_port.is_waiting_professional_state_active():
            return {}
        return {
            "terminal_mode": "SKIP_SILENT",
            "terminal_reason": "WAITING_PROFESSIONAL_SILENT",
            "terminal_text": None,
        }

    def _build_prompt_context(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        if state.runtime_context is None:
            return {}
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        prompt_preview = runtime_port.build_runtime_prompt_preview(state.runtime_context)
        return {
            "built_prompt_preview": prompt_preview,
        }

    def _call_llm(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.ConversationWorkflowRuntimePort,
            state.runtime_port,
        )
        return {
            "llm_response_text": runtime_port.generate_reply_with_tools(),
        }

    def _execute_tools(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        del state
        # Tool execution happens inside the existing webhook loop logic.
        return {}

    def _decide_terminal_output(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> dict[str, object]:
        if state.terminal_mode != "PENDING":
            return {}
        llm_response_text = state.llm_response_text
        if llm_response_text is None:
            return {
                "terminal_mode": "SKIP_SILENT",
                "terminal_reason": "WAITING_PROFESSIONAL_SILENT",
            }
        return {
            "terminal_mode": "SEND_MESSAGE",
            "terminal_reason": "AI_REPLY",
            "terminal_text": llm_response_text,
        }

    def _route_on_terminal(
        self,
        state: agentic_state_models.ConversationGraphState,
    ) -> str:
        if state.terminal_mode == "PENDING":
            return "continue"
        return "stop"
