import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service


class ConfirmRescheduledSlotHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "confirm_rescheduled_slot"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        input_dto = scheduling_dto.ConfirmRescheduledSlotInputDTO.model_validate(function_call.args)
        result = self._scheduling_service.confirm_rescheduled_slot(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            input_dto=input_dto,
        )
        return {
            "request_id": result.request_id,
            "status": result.status,
        }
