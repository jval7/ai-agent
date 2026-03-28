import pydantic

import src.infra.logs as app_logs
import src.services.agentic.guards.helpers as guard_helpers
import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class SelectProposedSlotToolInputDTO(pydantic.BaseModel):
    slot_option_number: str


class SelectProposedSlotHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "select_proposed_slot"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        tool_input = SelectProposedSlotToolInputDTO.model_validate(function_call.args)

        active_request = guard_helpers.find_single_active_request_waiting_patient_choice(
            scheduling_svc=self._scheduling_service,
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
        )
        if active_request is None:
            return {
                "status": "ERROR",
                "message": "No hay una solicitud activa esperando eleccion del paciente.",
            }

        option_number = str(int(tool_input.slot_option_number.strip()))
        slot_id = active_request.slot_options_map.get(option_number)
        if slot_id is None:
            return {
                "status": "ERROR",
                "message": (
                    f"La opcion {tool_input.slot_option_number} no existe. "
                    f"Opciones validas: {sorted(active_request.slot_options_map.keys(), key=int)}"
                ),
            }

        if not guard_helpers.request_contains_proposed_slot(
            request=active_request,
            slot_id=slot_id,
        ):
            return {
                "status": "ERROR",
                "message": f"El slot de la opcion {tool_input.slot_option_number} no esta disponible.",
            }

        try:
            self._scheduling_service.select_slot_for_confirmation(
                tenant_id=context.tenant_id,
                conversation_id=context.conversation_id,
                request_id=active_request.request_id,
                slot_id=slot_id,
            )
        except service_exceptions.ServiceError as error:
            logger.warning(
                "webhook.select_proposed_slot.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.select_proposed_slot.failed",
                        message="failed to select proposed slot",
                        data={
                            "tenant_id": context.tenant_id,
                            "conversation_id": context.conversation_id,
                            "request_id": active_request.request_id,
                            "slot_id": slot_id,
                            "error": str(error),
                        },
                    )
                },
            )
            return {
                "status": "ERROR",
                "message": "No se pudo registrar la seleccion del horario. Pide al paciente que reintente.",
            }

        return {
            "status": "SLOT_SELECTED",
            "slot_id": slot_id,
            "next_step": "inform_patient_about_payment",
        }
