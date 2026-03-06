import src.ports.agent_workflow_port as agent_workflow_port
import src.services.agentic.workflow_engine as workflow_engine
import src.services.dto.agent_workflow_dto as agent_workflow_dto


class FakeSchedulingRuntime(agent_workflow_port.SchedulingTransitionRuntimePort):
    def __init__(self) -> None:
        self.execution_order: list[str] = []

    def validate_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
    ) -> None:
        self.execution_order.append(f"validate:{input_dto.action}")

    def apply_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
    ) -> object:
        self.execution_order.append(f"apply:{input_dto.action}")
        return {
            "status": "OK",
            "payload": input_dto.payload,
        }

    def execute_side_effects(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> None:
        del transition_result
        self.execution_order.append(f"side_effects:{input_dto.action}")

    def persist_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> None:
        del transition_result
        self.execution_order.append(f"persist:{input_dto.action}")

    def build_output(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> object:
        self.execution_order.append(f"output:{input_dto.action}")
        return {
            "action": input_dto.action,
            "result": transition_result,
        }


def test_scheduling_transition_graph_executes_nodes_in_order() -> None:
    engine = workflow_engine.LangGraphAgentWorkflowEngine()
    runtime = FakeSchedulingRuntime()

    result = engine.run_scheduling_transition(
        input_dto=agent_workflow_dto.SchedulingTransitionInputDTO(
            action="SUBMIT_CONSULTATION_REASON",
            payload={"request_id": "req-1"},
        ),
        runtime_port=runtime,
    )

    assert result.action == "SUBMIT_CONSULTATION_REASON"
    assert result.result == {
        "action": "SUBMIT_CONSULTATION_REASON",
        "result": {
            "status": "OK",
            "payload": {"request_id": "req-1"},
        },
    }
    assert runtime.execution_order == [
        "validate:SUBMIT_CONSULTATION_REASON",
        "apply:SUBMIT_CONSULTATION_REASON",
        "side_effects:SUBMIT_CONSULTATION_REASON",
        "persist:SUBMIT_CONSULTATION_REASON",
        "output:SUBMIT_CONSULTATION_REASON",
    ]
