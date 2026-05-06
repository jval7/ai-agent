import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service


class SubmitRescheduleForReviewHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "submit_reschedule_for_review"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        input_dto = scheduling_dto.SubmitRescheduleForReviewToolInputDTO.model_validate(
            function_call.args
        )
        result = self._scheduling_service.submit_reschedule_for_review(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            whatsapp_user_id=context.whatsapp_user_id,
            input_dto=input_dto,
        )
        return {
            "request_id": result.request_id,
            "status": result.status,
            "round_number": result.round_number,
        }
