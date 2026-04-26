import typing

import pydantic

import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.infra.langsmith_tracer as langsmith_tracer
import src.infra.logs as app_logs
import src.ports.llm_provider_port as llm_provider_port
import src.ports.patient_repository_port as patient_repository_port
import src.services.agentic.prompt_builder as prompt_builder
import src.services.agentic.state_models as agentic_state_models
import src.services.agentic.tool_handlers.base as tool_handler_base
import src.services.agentic.tool_handlers.registry as tool_handler_registry_mod
import src.services.agentic.tool_registry as tool_registry
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class OrchestratorResult(pydantic.BaseModel):
    response_text: str | None = None
    early_return: bool = False
    iterations_used: int = 0


RuntimeContextResolver = typing.Callable[
    [str, str, patient_entity.Patient | None],
    agentic_state_models.RuntimePromptContext,
]


class ToolCallingOrchestrator:
    def __init__(
        self,
        llm_provider: llm_provider_port.LlmProviderPort,
        tool_handler_registry: tool_handler_registry_mod.ToolHandlerRegistry,
        prompt_builder_instance: prompt_builder.RuntimePromptBuilder,
        tool_definition_registry: tool_registry.ToolDefinitionRegistry,
        patient_repository: patient_repository_port.PatientRepositoryPort,
        tracer: langsmith_tracer.LangsmithTracer,
        max_iterations: int = 4,
        retry_backoff_seconds: list[float] | None = None,
        sleep_fn: typing.Callable[[float], None] | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._tool_handler_registry = tool_handler_registry
        self._prompt_builder = prompt_builder_instance
        self._tool_definition_registry = tool_definition_registry
        self._patient_repository = patient_repository
        self._tracer = tracer
        self._max_iterations = max_iterations
        self._retry_backoff_seconds = (
            retry_backoff_seconds if retry_backoff_seconds is not None else [0.5, 1.0]
        )
        if sleep_fn is not None:
            self._sleep_fn = sleep_fn
        else:
            import time

            self._sleep_fn = time.sleep

    def run(
        self,
        base_system_prompt: str,
        messages: list[llm_dto.ChatMessageDTO],
        tool_execution_context: tool_handler_base.ToolExecutionContext,
        known_patient: patient_entity.Patient | None,
        runtime_context_resolver: RuntimeContextResolver,
        agent_profile: agent_profile_entity.AgentProfile | None = None,
    ) -> OrchestratorResult:
        trace_inputs = {
            "tenant_id": tool_execution_context.tenant_id,
            "conversation_id": tool_execution_context.conversation_id,
            "whatsapp_user_id": tool_execution_context.whatsapp_user_id,
            "messages_count": len(messages),
            "known_patient_exists": known_patient is not None,
        }
        with self._tracer.trace(
            name="webhook.generate_reply_with_tools",
            run_type="chain",
            inputs=trace_inputs,
            tags=["webhook", "agent"],
        ) as trace_run:
            current_known_patient = known_patient
            function_call_results: list[list[llm_dto.FunctionCallResultDTO]] = []

            for iteration_index in range(self._max_iterations):
                runtime_context = runtime_context_resolver(
                    tool_execution_context.tenant_id,
                    tool_execution_context.conversation_id,
                    current_known_patient,
                )
                system_prompt = self._prompt_builder.compose_base_and_runtime_system_prompt(
                    base_system_prompt=base_system_prompt,
                    runtime_prompt=self._prompt_builder.build_runtime_system_prompt(
                        runtime_context=runtime_context,
                        known_patient=current_known_patient,
                        agent_profile=agent_profile,
                    ),
                )
                tool_definitions = self._tool_definition_registry.build_tool_definitions(
                    enabled_tool_names=runtime_context.enabled_tool_names,
                )
                llm_input = llm_dto.GenerateReplyInputDTO(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tool_definitions,
                    function_call_results=function_call_results,
                )
                trace_run.add_metadata(
                    {
                        "runtime_state": runtime_context.state,
                        "runtime_enabled_tools": runtime_context.enabled_tool_names,
                        "runtime_request_id": runtime_context.request_id,
                    }
                )
                llm_reply = self._request_llm_reply_with_retry(
                    tenant_id=tool_execution_context.tenant_id,
                    conversation_id=tool_execution_context.conversation_id,
                    llm_input=llm_input,
                )

                if llm_reply.function_calls:
                    trace_run.add_metadata(
                        {
                            "last_iteration": iteration_index + 1,
                            "last_function_calls_count": len(llm_reply.function_calls),
                        }
                    )
                    iteration_results: list[llm_dto.FunctionCallResultDTO] = []
                    for function_call in llm_reply.function_calls:
                        function_response_payload = self._tool_handler_registry.execute(
                            tool_execution_context,
                            function_call,
                        )
                        iteration_results.append(
                            llm_dto.FunctionCallResultDTO(
                                function_call=function_call,
                                function_response=llm_dto.FunctionResponseDTO(
                                    name=function_call.name,
                                    response=function_response_payload,
                                    call_id=function_call.call_id,
                                ),
                            )
                        )
                        if (
                            function_call.name == "submit_consultation_reason_for_review"
                            and function_response_payload.get("status")
                            == "AWAITING_CONSULTATION_REVIEW"
                        ):
                            trace_run.set_outputs(
                                {
                                    "outcome": "submit_consultation_reason_ack",
                                    "iteration": iteration_index + 1,
                                }
                            )
                            return OrchestratorResult(
                                response_text=_REASON_REVIEW_ACK_MESSAGE,
                                early_return=True,
                                iterations_used=iteration_index + 1,
                            )
                        if function_call.name == "confirm_selected_slot_and_create_event":
                            current_known_patient = self._patient_repository.get_by_whatsapp_user(
                                tenant_id=tool_execution_context.tenant_id,
                                whatsapp_user_id=tool_execution_context.whatsapp_user_id,
                            )
                    function_call_results.append(iteration_results)
                    continue

                if llm_reply.content.strip():
                    trace_run.set_outputs(
                        {
                            "outcome": "assistant_text",
                            "content_chars": len(llm_reply.content),
                            "iteration": iteration_index + 1,
                        }
                    )
                    return OrchestratorResult(
                        response_text=llm_reply.content,
                        iterations_used=iteration_index + 1,
                    )
                continue

            trace_run.set_error("llm returned empty content")
            raise service_exceptions.ExternalProviderError("llm returned empty content")

    def _request_llm_reply_with_retry(
        self,
        tenant_id: str,
        conversation_id: str,
        llm_input: llm_dto.GenerateReplyInputDTO,
    ) -> llm_dto.AgentReplyDTO:
        max_attempts = len(self._retry_backoff_seconds) + 1
        for attempt in range(max_attempts):
            try:
                llm_reply = self._llm_provider.generate_reply(llm_input)
                if llm_reply.function_calls:
                    return llm_reply
                if llm_reply.content.strip():
                    return llm_reply
                raise service_exceptions.ExternalProviderError("llm returned empty content")
            except service_exceptions.ExternalProviderError as error:
                error_message = str(error)
                if "empty content" not in error_message.lower():
                    raise

                if attempt >= len(self._retry_backoff_seconds):
                    raise

                delay_seconds = self._retry_backoff_seconds[attempt]
                logger.warning(
                    "webhook.llm.retry_empty_content",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.retry_empty_content",
                            message="retrying llm generation because provider returned empty content",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation_id,
                                "attempt": attempt + 1,
                                "delay_seconds": delay_seconds,
                            },
                        )
                    },
                )
                self._sleep_fn(delay_seconds)

        raise service_exceptions.ExternalProviderError("llm returned empty content")


_REASON_REVIEW_ACK_MESSAGE = (
    "Gracias por compartir la información. Dame un momento y te ayudo a continuar."
)
