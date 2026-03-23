import src.domain.entities.patient as patient_entity
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.agent_workflow_port as agent_workflow_port
import src.services.agentic.guards.base as guard_base
import src.services.agentic.guards.numeric_slot_selection_guard as numeric_slot_guard_mod
import src.services.agentic.guards.waiting_patient_choice_guard as patient_choice_guard_mod
import src.services.agentic.guards.waiting_professional_override_guard as professional_override_guard_mod
import src.services.agentic.guards.waiting_professional_silent_guard as professional_silent_guard_mod
import src.services.agentic.prompt_builder as prompt_builder
import src.services.agentic.runtime_context_resolver as runtime_context_resolver_mod
import src.services.agentic.state_models as agentic_state_models
import src.services.agentic.tool_calling_orchestrator as tool_calling_orchestrator_mod
import src.services.agentic.tool_handlers.base as tool_handler_base
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions

RuntimePromptContext = agentic_state_models.RuntimePromptContext


class WebhookConversationWorkflowRuntimeAdapter(
    agent_workflow_port.ConversationWorkflowRuntimePort
):
    def __init__(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        latest_user_text: str,
        llm_messages: list[llm_dto.ChatMessageDTO],
        known_patient: patient_entity.Patient | None,
        runtime_context_resolver: runtime_context_resolver_mod.RuntimeContextResolver,
        prompt_builder_instance: prompt_builder.RuntimePromptBuilder,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        tool_calling_orchestrator: tool_calling_orchestrator_mod.ToolCallingOrchestrator,
        patient_choice_guard: patient_choice_guard_mod.WaitingPatientChoiceGuard | None = None,
        numeric_slot_guard: numeric_slot_guard_mod.NumericSlotSelectionGuard | None = None,
        professional_override_guard: professional_override_guard_mod.WaitingProfessionalOverrideGuard
        | None = None,
        professional_silent_guard: professional_silent_guard_mod.WaitingProfessionalSilentGuard
        | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._conversation_id = conversation_id
        self._whatsapp_user_id = whatsapp_user_id
        self._latest_user_text = latest_user_text
        self._llm_messages = llm_messages
        self._known_patient = known_patient
        self._runtime_context_resolver = runtime_context_resolver
        self._prompt_builder = prompt_builder_instance
        self._agent_profile_repository = agent_profile_repository
        self._tool_calling_orchestrator = tool_calling_orchestrator
        self._patient_choice_guard = patient_choice_guard
        self._numeric_slot_guard = numeric_slot_guard
        self._professional_override_guard = professional_override_guard
        self._professional_silent_guard = professional_silent_guard

    def load_runtime_prompt_context(self) -> RuntimePromptContext:
        return self._runtime_context_resolver.resolve(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            known_patient=self._known_patient,
        )

    def handle_waiting_patient_choice_override(self) -> str | None:
        if self._patient_choice_guard is None:
            return None
        context = guard_base.GuardContext(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id=self._whatsapp_user_id,
            latest_user_text=self._latest_user_text,
        )
        return self._patient_choice_guard.evaluate(context)

    def enforce_required_numeric_slot_selection(self) -> str | None:
        if self._numeric_slot_guard is None:
            return None
        context = guard_base.GuardContext(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id="",
            latest_user_text=self._latest_user_text,
        )
        return self._numeric_slot_guard.evaluate(context)

    def handle_waiting_professional_override(self) -> str | None:
        if self._professional_override_guard is None:
            return None
        context = guard_base.GuardContext(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id=self._whatsapp_user_id,
            latest_user_text=self._latest_user_text,
        )
        return self._professional_override_guard.evaluate(context)

    def is_waiting_professional_state_active(self) -> bool:
        if self._professional_silent_guard is None:
            return False
        context = guard_base.GuardContext(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id="",
            latest_user_text="",
        )
        return self._professional_silent_guard.is_active(context)

    def build_runtime_prompt_preview(
        self,
        runtime_context: RuntimePromptContext,
    ) -> str:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(self._tenant_id)
        if agent_profile is None:
            raise service_exceptions.ExternalProviderError(
                "agent system prompt is not configured for this tenant"
            )
        base_prompt = agent_profile.system_prompt
        runtime_prompt = self._prompt_builder.build_runtime_system_prompt(
            runtime_context=runtime_context,
            known_patient=self._known_patient,
        )
        return self._prompt_builder.compose_base_and_runtime_system_prompt(
            base_system_prompt=base_prompt,
            runtime_prompt=runtime_prompt,
        )

    def generate_reply_with_tools(self) -> str:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(self._tenant_id)
        if agent_profile is None:
            raise service_exceptions.ExternalProviderError(
                "agent system prompt is not configured for this tenant"
            )
        tool_context = tool_handler_base.ToolExecutionContext(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id=self._whatsapp_user_id,
        )
        result = self._tool_calling_orchestrator.run(
            base_system_prompt=agent_profile.system_prompt,
            messages=self._llm_messages,
            tool_execution_context=tool_context,
            known_patient=self._known_patient,
            runtime_context_resolver=self._runtime_context_resolver.resolve,
        )
        if result.response_text is None:
            raise service_exceptions.ExternalProviderError("llm returned empty content")
        return result.response_text
