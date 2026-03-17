import src.ports.llm_provider_port as llm_provider_port
import src.services.agentic.guards.base as base
import src.services.agentic.guards.helpers as guard_helpers
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service


class NumericSlotSelectionGuard(base.ConversationGuard):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
        llm_provider: llm_provider_port.LlmProviderPort,
    ) -> None:
        self._scheduling_service = scheduling_svc
        self._llm_provider = llm_provider

    def evaluate(self, context: base.GuardContext) -> str | None:
        active_request = guard_helpers.find_single_active_request_waiting_patient_choice(
            scheduling_svc=self._scheduling_service,
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
        )
        if active_request is None:
            return None
        if active_request.selected_slot_id is not None:
            return None

        slot_id = guard_helpers.resolve_slot_id_from_option_number(
            request=active_request,
            latest_user_text=context.latest_user_text,
        )
        if slot_id is None:
            slot_id = guard_helpers.resolve_slot_id_from_natural_language(
                request=active_request,
                latest_user_text=context.latest_user_text,
                llm_provider=self._llm_provider,
            )
        if slot_id is None:
            return guard_helpers.build_slot_selection_retry_message(active_request)

        try:
            self._scheduling_service.select_slot_for_confirmation(
                tenant_id=context.tenant_id,
                conversation_id=context.conversation_id,
                request_id=active_request.request_id,
                slot_id=slot_id,
            )
        except service_exceptions.ServiceError:
            return guard_helpers.build_slot_selection_retry_message(active_request)
        return guard_helpers.build_payment_instructions_message(active_request.audience_type)
