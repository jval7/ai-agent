import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.use_cases.scheduling_service as scheduling_service


class ConfirmAttendanceReceivedHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "confirm_attendance_received"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        del function_call
        result = self._scheduling_service.close_attendance_confirmation(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
        )
        return {"status": result["status"], "action": result["action"]}
