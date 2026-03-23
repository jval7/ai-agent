import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service


class SubmitConsultationReasonHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "submit_consultation_reason_for_review"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        review_input_dto = (
            scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO.model_validate(
                function_call.args
            )
        )
        request = self._scheduling_service.submit_consultation_reason_for_review(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            whatsapp_user_id=context.whatsapp_user_id,
            input_dto=review_input_dto,
        )
        return {
            "request_id": request.request_id,
            "status": request.status,
            "round_number": request.round_number,
        }
