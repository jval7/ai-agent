import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.llm_provider_port as llm_provider_port
import src.services.agentic.guards.base as base
import src.services.agentic.guards.helpers as guard_helpers
import src.services.agentic.tool_handlers.base as tool_handler_base
import src.services.agentic.tool_handlers.registry as tool_handler_registry_mod
import src.services.agentic.tool_registry as tool_registry
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service


class WaitingProfessionalOverrideGuard(base.ConversationGuard):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService | None,
        llm_provider: llm_provider_port.LlmProviderPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        tool_handler_registry: tool_handler_registry_mod.ToolHandlerRegistry,
        tool_definition_registry: tool_registry.ToolDefinitionRegistry,
    ) -> None:
        self._scheduling_service = scheduling_svc
        self._llm_provider = llm_provider
        self._conversation_repository = conversation_repository
        self._tool_handler_registry = tool_handler_registry
        self._tool_definition_registry = tool_definition_registry

    def evaluate(self, context: base.GuardContext) -> str | None:
        waiting_request = self._find_latest_waiting_professional_request(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
        )
        if waiting_request is None:
            return None

        function_calls = self._resolve_override_function_calls(
            latest_user_text=context.latest_user_text,
            waiting_request_status=waiting_request.status,
        )
        if not function_calls:
            return None

        tool_context = tool_handler_base.ToolExecutionContext(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            whatsapp_user_id=context.whatsapp_user_id,
        )
        return guard_helpers.execute_override_function_calls(
            function_calls=function_calls,
            llm_provider=self._llm_provider,
            conversation_repository=self._conversation_repository,
            tool_handler_registry=self._tool_handler_registry,
            context=tool_context,
            latest_user_text=context.latest_user_text,
            log_event_prefix="waiting_override",
        )

    def _find_latest_waiting_professional_request(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO | None:
        if self._scheduling_service is None:
            return None
        del tenant_id
        del conversation_id
        return None

    def _resolve_override_function_calls(
        self,
        latest_user_text: str,
        waiting_request_status: str,
    ) -> list[llm_dto.FunctionCallDTO]:
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=(
                "Clasifica si el paciente pidio explicitamente: "
                "1) hablar con un humano, o 2) cancelar el proceso actual. "
                "Si no hay una peticion explicita de humano o cancelacion, "
                "no llames ninguna funcion y responde vacio. "
                "No llames otras funciones."
            ),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=(
                        f"Estado actual interno: {waiting_request_status}\\n"
                        f"Mensaje del paciente: {latest_user_text}\\n"
                        "Si pide explicitamente humano, llama handoff_to_human. "
                        "Si pide explicitamente cancelar, llama cancel_active_scheduling_request."
                    ),
                )
            ],
            tools=self._tool_definition_registry.build_waiting_state_tool_definitions(),
        )
        try:
            llm_reply = self._llm_provider.generate_reply(llm_input)
        except service_exceptions.ExternalProviderError:
            return []
        return llm_reply.function_calls
