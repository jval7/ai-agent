import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service


class HandoffToHumanHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "handoff_to_human"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        handoff_input_dto = scheduling_dto.HandoffToHumanInputDTO.model_validate(function_call.args)
        handoff_result = self._scheduling_service.handoff_to_human(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            input_dto=handoff_input_dto,
        )
        return {
            "status": handoff_result["status"],
            "control_mode": handoff_result["control_mode"],
        }
