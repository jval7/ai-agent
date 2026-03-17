import src.services.agentic.tool_handlers.base as base
import src.services.agentic.tool_handlers.patient_profile_resolver as patient_profile_resolver
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto


class ConfirmSlotHandler(base.ToolHandler):
    def __init__(
        self,
        resolver: patient_profile_resolver.PatientProfileResolver,
    ) -> None:
        self._resolver = resolver

    def tool_name(self) -> str:
        return "confirm_selected_slot_and_create_event"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        confirm_tool_input_dto = scheduling_dto.ConfirmSelectedSlotToolInputDTO.model_validate(
            function_call.args
        )
        resolved_confirm_selection = self._resolver.resolve_confirm_selected_slot_input(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            tool_input_dto=confirm_tool_input_dto,
        )
        confirm_result = self._resolver.confirm_selected_slot_with_retry(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            confirm_input_dto=resolved_confirm_selection.confirm_input_dto,
        )
        if confirm_result.get("status") == "BOOKED":
            self._resolver.create_patient_after_successful_booking(
                tenant_id=context.tenant_id,
                whatsapp_user_id=resolved_confirm_selection.whatsapp_user_id,
                patient_profile=resolved_confirm_selection.patient_profile,
                patient_exists=resolved_confirm_selection.patient_exists,
            )
        return confirm_result
