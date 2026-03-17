import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service


class CancelActiveRequestHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "cancel_active_scheduling_request"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        cancel_input_dto = scheduling_dto.CancelActiveSchedulingRequestInputDTO.model_validate(
            function_call.args
        )
        cancelled_request = self._scheduling_service.cancel_active_request(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            input_dto=cancel_input_dto,
        )
        return {
            "request_id": cancelled_request.request_id,
            "status": cancelled_request.status,
        }
