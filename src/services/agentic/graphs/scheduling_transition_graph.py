import typing

import langgraph.graph as langgraph_graph

import src.ports.agent_workflow_port as agent_workflow_port
import src.services.agentic.state_models as agentic_state_models
import src.services.dto.agent_workflow_dto as agent_workflow_dto


class SchedulingTransitionGraph:
    def __init__(self) -> None:
        state_graph = langgraph_graph.StateGraph(
            agentic_state_models.SchedulingTransitionGraphState
        )
        state_graph.add_node("validate_transition", self._validate_transition)
        state_graph.add_node("apply_transition", self._apply_transition)
        state_graph.add_node("execute_side_effects", self._execute_side_effects)
        state_graph.add_node("persist_transition", self._persist_transition)
        state_graph.add_node("build_output", self._build_output)

        state_graph.add_edge(langgraph_graph.START, "validate_transition")
        state_graph.add_edge("validate_transition", "apply_transition")
        state_graph.add_edge("apply_transition", "execute_side_effects")
        state_graph.add_edge("execute_side_effects", "persist_transition")
        state_graph.add_edge("persist_transition", "build_output")
        state_graph.add_edge("build_output", langgraph_graph.END)
        self._graph = state_graph.compile()

    def run(
        self,
        state: agentic_state_models.SchedulingTransitionGraphState,
    ) -> agentic_state_models.SchedulingTransitionGraphState:
        output = typing.cast(typing.Any, self._graph).invoke(state.model_dump(mode="python"))
        return agentic_state_models.SchedulingTransitionGraphState.model_validate(output)

    def _validate_transition(
        self,
        state: agentic_state_models.SchedulingTransitionGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.SchedulingTransitionRuntimePort,
            state.runtime_port,
        )
        input_dto = self._build_input_dto(
            action=state.action,
            payload=state.input_payload,
        )
        runtime_port.validate_transition(input_dto)
        return {"validated": True}

    def _apply_transition(
        self,
        state: agentic_state_models.SchedulingTransitionGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.SchedulingTransitionRuntimePort,
            state.runtime_port,
        )
        input_dto = self._build_input_dto(
            action=state.action,
            payload=state.input_payload,
        )
        transition_result = runtime_port.apply_transition(input_dto)
        return {"transition_result": transition_result}

    def _execute_side_effects(
        self,
        state: agentic_state_models.SchedulingTransitionGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.SchedulingTransitionRuntimePort,
            state.runtime_port,
        )
        input_dto = self._build_input_dto(
            action=state.action,
            payload=state.input_payload,
        )
        runtime_port.execute_side_effects(input_dto, state.transition_result)
        return {"side_effects_executed": True}

    def _persist_transition(
        self,
        state: agentic_state_models.SchedulingTransitionGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.SchedulingTransitionRuntimePort,
            state.runtime_port,
        )
        input_dto = self._build_input_dto(
            action=state.action,
            payload=state.input_payload,
        )
        runtime_port.persist_transition(input_dto, state.transition_result)
        return {"persisted": True}

    def _build_output(
        self,
        state: agentic_state_models.SchedulingTransitionGraphState,
    ) -> dict[str, object]:
        runtime_port = typing.cast(
            agent_workflow_port.SchedulingTransitionRuntimePort,
            state.runtime_port,
        )
        input_dto = self._build_input_dto(
            action=state.action,
            payload=state.input_payload,
        )
        transition_output = runtime_port.build_output(input_dto, state.transition_result)
        return {"transition_output": transition_output}

    def _build_input_dto(
        self,
        action: str,
        payload: object | None,
    ) -> agent_workflow_dto.SchedulingTransitionInputDTO:
        return agent_workflow_dto.SchedulingTransitionInputDTO(
            action=typing.cast(
                typing.Literal[
                    "SUBMIT_CONSULTATION_REASON",
                    "RESOLVE_CONSULTATION_REVIEW",
                    "SELECT_SLOT_FOR_CONFIRMATION",
                    "CONFIRM_SLOT_AND_CREATE_EVENT",
                    "CANCEL_ACTIVE_REQUEST",
                    "HANDOFF_TO_HUMAN",
                    "RESCHEDULE_BOOKED_SLOT",
                    "CANCEL_BOOKED_SLOT",
                    "UPDATE_BOOKED_PAYMENT",
                ],
                action,
            ),
            payload=payload,
        )
