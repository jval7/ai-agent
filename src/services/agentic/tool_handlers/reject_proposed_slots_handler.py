import pydantic

import src.infra.logs as app_logs
import src.services.agentic.guards.helpers as guard_helpers
import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class RejectProposedSlotsToolInputDTO(pydantic.BaseModel):
    patient_preference: str


class RejectProposedSlotsHandler(base.ToolHandler):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def tool_name(self) -> str:
        return "reject_proposed_slots"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        tool_input = RejectProposedSlotsToolInputDTO.model_validate(function_call.args)

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

        try:
            self._scheduling_service.escalate_patient_slot_rejection(
                tenant_id=context.tenant_id,
                request_id=active_request.request_id,
                patient_preference_note=tool_input.patient_preference,
            )
        except service_exceptions.ServiceError as error:
            logger.warning(
                "webhook.reject_proposed_slots.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.reject_proposed_slots.failed",
                        message="failed to escalate patient slot rejection",
                        data={
                            "tenant_id": context.tenant_id,
                            "conversation_id": context.conversation_id,
                            "request_id": active_request.request_id,
                            "error": str(error),
                        },
                    )
                },
            )
            return {
                "status": "ERROR",
                "message": "No se pudo registrar el rechazo. El profesional sera notificado por otro medio.",
            }

        return {
            "status": "ESCALATED_TO_PROFESSIONAL",
            "message": "Se notifico al profesional para proponer nuevos horarios.",
        }
