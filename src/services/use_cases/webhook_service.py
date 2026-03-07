import re
import time
import typing
import unicodedata

import pydantic

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.infra.langsmith_tracer as langsmith_tracer
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.agent_workflow_port as agent_workflow_port
import src.ports.blacklist_repository_port as blacklist_repository_port
import src.ports.clock_port as clock_port
import src.ports.conversation_processing_lock_port as conversation_processing_lock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.llm_provider_port as llm_provider_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.agentic.prompt_builder as prompt_builder
import src.services.agentic.state_models as agentic_state_models
import src.services.agentic.tool_registry as tool_registry
import src.services.agentic.workflow_engine as workflow_engine
import src.services.dto.agent_workflow_dto as agent_workflow_dto
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.scheduling_slot_formatter as scheduling_slot_formatter
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class ResolvedPatientProfile(pydantic.BaseModel):
    full_name: str
    email: str
    age: int
    consultation_reason: str
    location: str
    phone: str


class ResolvedConfirmSelection(pydantic.BaseModel):
    confirm_input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO
    patient_profile: ResolvedPatientProfile
    patient_exists: bool
    whatsapp_user_id: str


RuntimePromptContext = agentic_state_models.RuntimePromptContext


class WebhookConversationWorkflowRuntimeAdapter(
    agent_workflow_port.ConversationWorkflowRuntimePort
):
    def __init__(
        self,
        webhook_service: "WebhookService",
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        latest_user_text: str,
        llm_messages: list[llm_dto.ChatMessageDTO],
        known_patient: patient_entity.Patient | None,
    ) -> None:
        self._webhook_service = webhook_service
        self._tenant_id = tenant_id
        self._conversation_id = conversation_id
        self._whatsapp_user_id = whatsapp_user_id
        self._latest_user_text = latest_user_text
        self._llm_messages = llm_messages
        self._known_patient = known_patient

    def load_runtime_prompt_context(self) -> RuntimePromptContext:
        return self._webhook_service._resolve_runtime_prompt_context(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            known_patient=self._known_patient,
        )

    def handle_waiting_patient_choice_override(self) -> str | None:
        return self._webhook_service._handle_waiting_patient_choice_state_message(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id=self._whatsapp_user_id,
            latest_user_text=self._latest_user_text,
        )

    def enforce_required_numeric_slot_selection(self) -> str | None:
        return self._webhook_service._enforce_required_numeric_slot_selection(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            latest_user_text=self._latest_user_text,
        )

    def handle_waiting_professional_override(self) -> str | None:
        return self._webhook_service._handle_waiting_professional_state_message(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id=self._whatsapp_user_id,
            latest_user_text=self._latest_user_text,
        )

    def is_waiting_professional_state_active(self) -> bool:
        return self._webhook_service._is_waiting_professional_state_active(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
        )

    def build_runtime_prompt_preview(
        self,
        runtime_context: RuntimePromptContext,
    ) -> str:
        base_prompt = self._webhook_service._resolve_agent_system_prompt(self._tenant_id)
        runtime_prompt = self._webhook_service._prompt_builder.build_runtime_system_prompt(
            runtime_context=runtime_context,
            known_patient=self._known_patient,
        )
        return self._webhook_service._prompt_builder.compose_base_and_runtime_system_prompt(
            base_system_prompt=base_prompt,
            runtime_prompt=runtime_prompt,
        )

    def generate_reply_with_tools(self) -> str:
        return self._webhook_service._generate_reply_with_tools(
            tenant_id=self._tenant_id,
            conversation_id=self._conversation_id,
            whatsapp_user_id=self._whatsapp_user_id,
            llm_messages=self._llm_messages,
            known_patient=self._known_patient,
        )


class WebhookService:
    def __init__(
        self,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        patient_repository: patient_repository_port.PatientRepositoryPort,
        processed_webhook_event_repository: (
            processed_webhook_event_repository_port.ProcessedWebhookEventRepositoryPort
        ),
        blacklist_repository: blacklist_repository_port.BlacklistRepositoryPort,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        scheduling_service: scheduling_service.SchedulingService | None,
        llm_provider: llm_provider_port.LlmProviderPort,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        default_system_prompt: str,
        context_message_limit: int,
        tracer: langsmith_tracer.LangsmithTracer | None = None,
        sleep_seconds: typing.Callable[[float], None] | None = None,
        agent_workflow: agent_workflow_port.AgentWorkflowPort | None = None,
        runtime_prompt_builder: prompt_builder.RuntimePromptBuilder | None = None,
        tool_definition_registry: tool_registry.ToolDefinitionRegistry | None = None,
        conversation_processing_lock: conversation_processing_lock_port.ConversationProcessingLockPort
        | None = None,
    ) -> None:
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._conversation_repository = conversation_repository
        self._patient_repository = patient_repository
        self._processed_webhook_event_repository = processed_webhook_event_repository
        self._blacklist_repository = blacklist_repository
        self._agent_profile_repository = agent_profile_repository
        self._conversation_processing_lock = conversation_processing_lock
        self._scheduling_service = scheduling_service
        self._llm_provider = llm_provider
        self._whatsapp_provider = whatsapp_provider
        self._id_generator = id_generator
        self._clock = clock
        self._default_system_prompt = default_system_prompt
        self._context_message_limit = context_message_limit
        self._agent_workflow: agent_workflow_port.AgentWorkflowPort
        if agent_workflow is None:
            self._agent_workflow = workflow_engine.LangGraphAgentWorkflowEngine()
        else:
            self._agent_workflow = agent_workflow
        if runtime_prompt_builder is None:
            self._prompt_builder = prompt_builder.RuntimePromptBuilder()
        else:
            self._prompt_builder = runtime_prompt_builder
        if tool_definition_registry is None:
            self._tool_registry = tool_registry.ToolDefinitionRegistry()
        else:
            self._tool_registry = tool_definition_registry
        if tracer is None:
            self._tracer = langsmith_tracer.LangsmithTracer()
        else:
            self._tracer = tracer
        self._max_function_call_iterations = 4
        self._max_debounce_reprocess_iterations = 3
        self._google_network_retry_backoff_seconds = [1.0, 2.0, 4.0]
        self._llm_empty_content_retry_backoff_seconds = [0.5, 1.0]
        self._professional_signature = "Psi. Alejandra Escobar"
        self._email_pattern = re.compile(
            r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
        )
        self._trace_email_pattern = re.compile(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
        )
        self._trace_phone_pattern = re.compile(r"\+?\d{7,15}")
        self._numeric_pattern = re.compile(r"^\d+$")
        if sleep_seconds is not None:
            self._sleep_seconds = sleep_seconds
        else:
            self._sleep_seconds = time.sleep

    def process_payload(self, payload: dict[str, object]) -> webhook_dto.WebhookEventResponseDTO:
        events = self._whatsapp_provider.parse_incoming_message_events(payload)
        logger.info(
            "webhook.received",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.received",
                    message="webhook payload parsed",
                    data={"event_count": len(events)},
                )
            },
        )
        for event in events:
            try:
                self._process_event(event)
            except service_exceptions.ServiceError as error:
                self._mark_event_failed_by_phone_number(
                    phone_number_id=event.phone_number_id,
                    provider_event_id=event.provider_event_id,
                    failure_reason=str(error),
                )
                raise
            except ValueError as error:
                self._mark_event_failed_by_phone_number(
                    phone_number_id=event.phone_number_id,
                    provider_event_id=event.provider_event_id,
                    failure_reason=str(error),
                )
                raise
        return webhook_dto.WebhookEventResponseDTO(status="processed")

    def _process_event(self, event: webhook_dto.IncomingMessageEventDTO) -> None:
        connection = self._whatsapp_connection_repository.get_by_phone_number_id(
            event.phone_number_id
        )
        if connection is None:
            logger.warning(
                "webhook.event.skipped",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.event.skipped",
                        message="webhook event skipped because phone number is not connected",
                        data={
                            "phone_number_id": event.phone_number_id,
                            "provider_event_id": event.provider_event_id,
                        },
                    )
                },
            )
            return

        tenant_id = connection.tenant_id
        event_claimed = self._processed_webhook_event_repository.claim_for_processing(
            tenant_id=tenant_id,
            provider_event_id=event.provider_event_id,
            claimed_at=self._clock.now(),
        )
        if not event_claimed:
            logger.info(
                "webhook.duplicate_skipped",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.duplicate_skipped",
                        message="duplicate webhook event skipped",
                        data={
                            "tenant_id": tenant_id,
                            "provider_event_id": event.provider_event_id,
                        },
                    )
                },
            )
            return

        if self._blacklist_repository.exists(tenant_id, event.whatsapp_user_id):
            logger.info(
                "webhook.blacklist_blocked",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.blacklist_blocked",
                        message="blacklisted whatsapp user skipped",
                        data={
                            "tenant_id": tenant_id,
                            "provider_event_id": event.provider_event_id,
                        },
                    )
                },
            )
            self._mark_event_processed(tenant_id, event.provider_event_id)
            return

        if connection.access_token is None or connection.phone_number_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")

        now_value = self._clock.now()
        whatsapp_user = self._conversation_repository.get_whatsapp_user(
            tenant_id,
            event.whatsapp_user_id,
        )
        if whatsapp_user is None:
            whatsapp_user = whatsapp_user_entity.WhatsappUser(
                id=event.whatsapp_user_id,
                tenant_id=tenant_id,
                display_name=event.whatsapp_user_name,
                created_at=now_value,
            )
            self._conversation_repository.save_whatsapp_user(whatsapp_user)

        conversation = self._conversation_repository.get_conversation_by_whatsapp_user(
            tenant_id,
            event.whatsapp_user_id,
        )
        if conversation is None:
            conversation = conversation_entity.Conversation(
                id=self._id_generator.new_id(),
                tenant_id=tenant_id,
                whatsapp_user_id=event.whatsapp_user_id,
                started_at=now_value,
                updated_at=now_value,
                last_message_preview=None,
                message_ids=[],
                control_mode="AI",
            )
            self._conversation_repository.save_conversation(conversation)

        if self._conversation_has_provider_message_id(conversation, event.message_id):
            self._mark_event_processed(tenant_id, event.provider_event_id)
            logger.info(
                "webhook.duplicate_message_skipped",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.duplicate_message_skipped",
                        message="duplicate webhook message id skipped",
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation.id,
                            "provider_event_id": event.provider_event_id,
                            "provider_message_id": event.message_id,
                        },
                    )
                },
            )
            return

        if event.source == "OWNER_APP":
            owner_message = message_entity.Message(
                id=self._id_generator.new_id(),
                conversation_id=conversation.id,
                tenant_id=tenant_id,
                direction="OUTBOUND",
                role="human_agent",
                content=event.message_text,
                provider_message_id=event.message_id,
                created_at=now_value,
            )
            self._conversation_repository.save_message(owner_message)
            conversation.append_message(
                owner_message.id,
                owner_message.content,
                owner_message.created_at,
            )
            conversation.set_control_mode("HUMAN", owner_message.created_at)
            self._conversation_repository.save_conversation(conversation)
            self._mark_event_processed(tenant_id, event.provider_event_id)
            logger.info(
                "webhook.owner_handoff_human",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.owner_handoff_human",
                        message="owner app message moved conversation to HUMAN mode",
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation.id,
                            "provider_event_id": event.provider_event_id,
                            "message_type": event.message_type,
                        },
                    )
                },
            )
            return

        inbound_message = message_entity.Message(
            id=self._id_generator.new_id(),
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            direction="INBOUND",
            role="user",
            content=event.message_text,
            provider_message_id=event.message_id,
            created_at=now_value,
        )
        self._conversation_repository.save_message(inbound_message)
        conversation.append_message(inbound_message.id, inbound_message.content, now_value)
        self._conversation_repository.save_conversation(conversation)

        if conversation.control_mode == "HUMAN":
            self._mark_event_processed(tenant_id, event.provider_event_id)
            logger.info(
                "webhook.human_mode_skip_ai",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.human_mode_skip_ai",
                        message="customer message persisted while conversation is in HUMAN mode",
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation.id,
                            "provider_event_id": event.provider_event_id,
                        },
                    )
                },
            )
            return

        lock_holder_id: str | None = None
        if self._conversation_processing_lock is not None:
            lock_holder_id = self._id_generator.new_id()
            lock_acquired = self._conversation_processing_lock.try_acquire(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                holder_id=lock_holder_id,
                acquired_at=self._clock.now(),
            )
            if not lock_acquired:
                self._mark_event_processed(tenant_id, event.provider_event_id)
                logger.info(
                    "webhook.debounce_deferred",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.debounce_deferred",
                            message="message persisted, another handler holds conversation lock",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation.id,
                                "provider_event_id": event.provider_event_id,
                            },
                        )
                    },
                )
                return

        try:
            self._process_ai_reply_with_debounce(
                connection=connection,
                conversation=conversation,
                tenant_id=tenant_id,
                event=event,
                inbound_message=inbound_message,
            )
        finally:
            if self._conversation_processing_lock is not None and lock_holder_id is not None:
                self._conversation_processing_lock.release(
                    tenant_id=tenant_id,
                    conversation_id=conversation.id,
                    holder_id=lock_holder_id,
                )

    def _process_ai_reply_with_debounce(
        self,
        connection: whatsapp_connection_entity.WhatsappConnection,
        conversation: conversation_entity.Conversation,
        tenant_id: str,
        event: webhook_dto.IncomingMessageEventDTO,
        inbound_message: message_entity.Message,
    ) -> None:
        messages_count_snapshot = len(
            self._conversation_repository.list_messages(tenant_id, conversation.id)
        )
        debounce_delay = self._resolve_debounce_delay_seconds(tenant_id)

        for debounce_iteration in range(self._max_debounce_reprocess_iterations):
            history = self._conversation_repository.list_messages(tenant_id, conversation.id)
            history_messages = history[-self._context_message_limit :]
            llm_messages: list[llm_dto.ChatMessageDTO] = []
            for message in history_messages:
                message_role = message.role
                if message_role == "human_agent":
                    message_role = "assistant"
                llm_messages.append(
                    llm_dto.ChatMessageDTO(role=message_role, content=message.content)
                )
            latest_user_text = (
                history_messages[-1].content if history_messages else inbound_message.content
            )
            known_patient = self._patient_repository.get_by_whatsapp_user(
                tenant_id=tenant_id,
                whatsapp_user_id=event.whatsapp_user_id,
            )
            subsessions_count_before_ai_reply = len(conversation.subsessions)

            trace_inputs: dict[str, object] = {
                "tenant_id": tenant_id,
                "conversation_id": conversation.id,
                "provider_event_id": event.provider_event_id,
                "message_type": event.message_type,
                "message_source": event.source,
                "message_preview": self._sanitize_trace_text(event.message_text),
                "history_messages_count": len(history_messages),
                "debounce_iteration": debounce_iteration,
            }
            with self._tracer.trace(
                name="webhook.process_event.ai_path",
                run_type="chain",
                inputs=trace_inputs,
                tags=["webhook"],
            ) as trace_run:
                try:
                    runtime_adapter = WebhookConversationWorkflowRuntimeAdapter(
                        webhook_service=self,
                        tenant_id=tenant_id,
                        conversation_id=conversation.id,
                        whatsapp_user_id=event.whatsapp_user_id,
                        latest_user_text=latest_user_text,
                        llm_messages=llm_messages,
                        known_patient=known_patient,
                    )
                    workflow_result = self._agent_workflow.run_conversation_flow(
                        input_dto=agent_workflow_dto.ConversationWorkflowInputDTO(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            whatsapp_user_id=event.whatsapp_user_id,
                            latest_user_text=latest_user_text,
                        ),
                        runtime_port=runtime_adapter,
                    )
                    trace_run.add_metadata(
                        {
                            "runtime_state": workflow_result.runtime_state,
                            "runtime_enabled_tools": workflow_result.enabled_tool_names,
                            "workflow_reason": workflow_result.reason,
                        }
                    )
                    if workflow_result.mode == "SKIP_SILENT":
                        trace_run.set_outputs(
                            {
                                "outcome": "skip_silent",
                                "workflow_reason": workflow_result.reason,
                            }
                        )
                        self._mark_event_processed(tenant_id, event.provider_event_id)
                        if workflow_result.reason == "WAITING_PROFESSIONAL_SILENT":
                            logger.info(
                                "webhook.waiting_professional_silent_skip",
                                extra={
                                    "event_data": app_logs.build_log_event(
                                        event_name="webhook.waiting_professional_silent_skip",
                                        message="customer message persisted and skipped while waiting professional response",
                                        data={
                                            "tenant_id": tenant_id,
                                            "conversation_id": conversation.id,
                                            "provider_event_id": event.provider_event_id,
                                        },
                                    )
                                },
                            )
                        return
                    if workflow_result.text is None:
                        raise service_exceptions.InvalidStateError(
                            "workflow returned SEND_MESSAGE without text"
                        )

                    if debounce_delay > 0:
                        self._sleep_seconds(debounce_delay)

                    fresh_messages = self._conversation_repository.list_messages(
                        tenant_id, conversation.id
                    )
                    if len(fresh_messages) > messages_count_snapshot:
                        messages_count_snapshot = len(fresh_messages)
                        trace_run.set_outputs(
                            {
                                "outcome": "debounce_reprocessing",
                                "debounce_iteration": debounce_iteration,
                            }
                        )
                        logger.info(
                            "webhook.debounce_reprocessing",
                            extra={
                                "event_data": app_logs.build_log_event(
                                    event_name="webhook.debounce_reprocessing",
                                    message="new messages arrived during processing, re-running with fresh history",
                                    data={
                                        "tenant_id": tenant_id,
                                        "conversation_id": conversation.id,
                                        "provider_event_id": event.provider_event_id,
                                        "debounce_iteration": debounce_iteration,
                                        "previous_count": messages_count_snapshot,
                                        "current_count": len(fresh_messages),
                                    },
                                )
                            },
                        )
                        continue

                    outbound_message_provider_id = self._send_assistant_message(
                        connection=connection,
                        conversation_id=conversation.id,
                        tenant_id=tenant_id,
                        whatsapp_user_id=event.whatsapp_user_id,
                        text=workflow_result.text,
                    )
                    if workflow_result.reason == "AI_REPLY":
                        self._archive_new_active_messages_into_latest_subsession_if_booking_occurred(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            subsessions_count_before_ai_reply=subsessions_count_before_ai_reply,
                        )
                except service_exceptions.ExternalProviderError as error:
                    trace_run.set_error(str(error))
                    logger.error(
                        "webhook.ai_reply_failed",
                        extra={
                            "event_data": app_logs.build_log_event(
                                event_name="webhook.ai_reply_failed",
                                message="ai reply generation or outbound send failed",
                                data={
                                    "tenant_id": tenant_id,
                                    "conversation_id": conversation.id,
                                    "provider_event_id": event.provider_event_id,
                                    "error_type": type(error).__name__,
                                    "error_message": str(error),
                                },
                            )
                        },
                    )
                    fallback_text = self._build_llm_failure_fallback_message(str(error))
                    try:
                        self._send_assistant_message(
                            connection=connection,
                            conversation_id=conversation.id,
                            tenant_id=tenant_id,
                            whatsapp_user_id=event.whatsapp_user_id,
                            text=fallback_text,
                        )
                        logger.warning(
                            "webhook.ai_reply_fallback_sent",
                            extra={
                                "event_data": app_logs.build_log_event(
                                    event_name="webhook.ai_reply_fallback_sent",
                                    message="fallback reply sent after ai generation failure",
                                    data={
                                        "tenant_id": tenant_id,
                                        "conversation_id": conversation.id,
                                        "provider_event_id": event.provider_event_id,
                                    },
                                )
                            },
                        )
                    except service_exceptions.ExternalProviderError as fallback_error:
                        logger.error(
                            "webhook.ai_reply_fallback_failed",
                            extra={
                                "event_data": app_logs.build_log_event(
                                    event_name="webhook.ai_reply_fallback_failed",
                                    message="fallback reply failed after ai generation failure",
                                    data={
                                        "tenant_id": tenant_id,
                                        "conversation_id": conversation.id,
                                        "provider_event_id": event.provider_event_id,
                                        "error_type": type(fallback_error).__name__,
                                        "error_message": str(fallback_error),
                                    },
                                )
                            },
                        )
                    self._mark_event_processed(tenant_id, event.provider_event_id)
                    return
                trace_run.set_outputs(
                    {
                        "outbound_provider_message_id": outbound_message_provider_id,
                        "workflow_reason": workflow_result.reason,
                    }
                )

            self._mark_event_processed(tenant_id, event.provider_event_id)
            self._log_workflow_outcome(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                provider_event_id=event.provider_event_id,
                outbound_message_provider_id=outbound_message_provider_id,
                workflow_reason=workflow_result.reason,
            )
            return

    def _log_workflow_outcome(
        self,
        tenant_id: str,
        conversation_id: str,
        provider_event_id: str,
        outbound_message_provider_id: str,
        workflow_reason: str,
    ) -> None:
        reason_log_map: dict[str, tuple[str, str]] = {
            "PATIENT_CHOICE_OVERRIDE": (
                "webhook.patient_choice_override_sent",
                "patient choice state override handled before numeric slot selection",
            ),
            "NUMERIC_SLOT_RETRY": (
                "webhook.slot_selection_retry_sent",
                "customer must choose a slot option by number before continuing",
            ),
            "WAITING_PROFESSIONAL_OVERRIDE": (
                "webhook.waiting_professional_override_sent",
                "customer requested explicit override while waiting professional response",
            ),
        }
        log_entry = reason_log_map.get(workflow_reason)
        if log_entry is not None:
            event_name, log_message = log_entry
            logger.info(
                event_name,
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name=event_name,
                        message=log_message,
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation_id,
                            "provider_event_id": provider_event_id,
                        },
                    )
                },
            )
            return

        logger.info(
            "webhook.ai_reply_sent",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.ai_reply_sent",
                    message="ai reply sent and persisted",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "provider_event_id": provider_event_id,
                        "outbound_provider_message_id": outbound_message_provider_id,
                    },
                )
            },
        )

    def _build_llm_failure_fallback_message(self, error_message: str) -> str:
        normalized_message = error_message.lower()
        if "empty content" in normalized_message:
            return (
                "Perdon, tuve un problema tecnico momentaneo al procesar tu mensaje. "
                "Ya recibi tu informacion, ¿podrias reenviarla en un solo mensaje para continuar?"
            )
        return (
            "Perdon, en este momento tengo una dificultad tecnica para continuar. "
            "Si deseas, puedo pasarte con una persona del equipo."
        )

    def _send_assistant_message(
        self,
        connection: whatsapp_connection_entity.WhatsappConnection,
        conversation_id: str,
        tenant_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        if connection.access_token is None or connection.phone_number_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")
        outbound_message_provider_id = self._whatsapp_provider.send_text_message(
            access_token=connection.access_token,
            phone_number_id=connection.phone_number_id,
            whatsapp_user_id=whatsapp_user_id,
            text=text,
        )
        outbound_message = message_entity.Message(
            id=self._id_generator.new_id(),
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            direction="OUTBOUND",
            role="assistant",
            content=text,
            provider_message_id=outbound_message_provider_id,
            created_at=self._clock.now(),
        )
        self._conversation_repository.save_message(outbound_message)
        latest_conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if latest_conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")
        latest_conversation.append_message(
            outbound_message.id,
            outbound_message.content,
            outbound_message.created_at,
        )
        self._conversation_repository.save_conversation(latest_conversation)
        return outbound_message_provider_id

    def _archive_new_active_messages_into_latest_subsession_if_booking_occurred(
        self,
        tenant_id: str,
        conversation_id: str,
        subsessions_count_before_ai_reply: int,
    ) -> None:
        latest_conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id,
            conversation_id,
        )
        if latest_conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        if len(latest_conversation.subsessions) <= subsessions_count_before_ai_reply:
            return

        latest_subsession = latest_conversation.subsessions[-1]
        active_messages = self._conversation_repository.list_messages(
            tenant_id,
            conversation_id,
        )
        if not active_messages:
            return

        sorted_active_messages = sorted(active_messages, key=lambda item: item.created_at)
        existing_message_ids = {message.id for message in latest_subsession.messages}
        appended_messages_count = 0
        for active_message in sorted_active_messages:
            if active_message.id in existing_message_ids:
                continue
            latest_subsession.messages.append(active_message.model_copy(deep=True))
            existing_message_ids.add(active_message.id)
            appended_messages_count += 1

        latest_conversation.messages = []
        latest_conversation.message_ids = []
        latest_conversation.last_message_preview = None
        latest_conversation.updated_at = self._clock.now()
        self._conversation_repository.save_conversation(latest_conversation)
        self._conversation_repository.delete_messages(tenant_id, conversation_id)
        logger.info(
            "webhook.booking_confirmation_message_archived",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.booking_confirmation_message_archived",
                    message=(
                        "booking confirmation message archived into latest booking subsession"
                    ),
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "appended_messages_count": appended_messages_count,
                        "subsessions_count": len(latest_conversation.subsessions),
                    },
                )
            },
        )

    def _generate_reply_with_tools(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        llm_messages: list[llm_dto.ChatMessageDTO],
        known_patient: patient_entity.Patient | None,
    ) -> str:
        trace_inputs = {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "whatsapp_user_id": whatsapp_user_id,
            "messages_count": len(llm_messages),
            "known_patient_exists": known_patient is not None,
        }
        with self._tracer.trace(
            name="webhook.generate_reply_with_tools",
            run_type="chain",
            inputs=trace_inputs,
            tags=["webhook", "agent"],
        ) as trace_run:
            base_system_prompt = self._resolve_agent_system_prompt(tenant_id)
            current_known_patient = known_patient
            function_call_results: list[llm_dto.FunctionCallResultDTO] = []
            for iteration_index in range(self._max_function_call_iterations):
                runtime_prompt_context = self._resolve_runtime_prompt_context(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    known_patient=current_known_patient,
                )
                system_prompt = self._compose_base_and_runtime_system_prompt(
                    base_system_prompt=base_system_prompt,
                    runtime_prompt=self._build_runtime_system_prompt(
                        runtime_context=runtime_prompt_context,
                        known_patient=current_known_patient,
                    ),
                )
                tool_definitions = self._build_tool_definitions(
                    enabled_tool_names=runtime_prompt_context.enabled_tool_names
                )
                llm_input = llm_dto.GenerateReplyInputDTO(
                    system_prompt=system_prompt,
                    messages=llm_messages,
                    tools=tool_definitions,
                    function_call_results=function_call_results,
                )
                trace_run.add_metadata(
                    {
                        "runtime_state": runtime_prompt_context.state,
                        "runtime_enabled_tools": runtime_prompt_context.enabled_tool_names,
                        "runtime_request_id": runtime_prompt_context.request_id,
                    }
                )
                llm_reply = self._request_llm_reply_with_retry(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    llm_input=llm_input,
                )
                if llm_reply.function_calls:
                    trace_run.add_metadata(
                        {
                            "last_iteration": iteration_index + 1,
                            "last_function_calls_count": len(llm_reply.function_calls),
                        }
                    )
                    for function_call in llm_reply.function_calls:
                        function_response_payload = self._execute_function_call(
                            tenant_id=tenant_id,
                            conversation_id=conversation_id,
                            whatsapp_user_id=whatsapp_user_id,
                            function_call=function_call,
                        )
                        function_call_results.append(
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
                            return self._build_reason_review_ack_message()
                        if function_call.name == "confirm_selected_slot_and_create_event":
                            current_known_patient = self._patient_repository.get_by_whatsapp_user(
                                tenant_id=tenant_id,
                                whatsapp_user_id=whatsapp_user_id,
                            )
                    continue

                if llm_reply.content.strip():
                    trace_run.set_outputs(
                        {
                            "outcome": "assistant_text",
                            "content_chars": len(llm_reply.content),
                            "iteration": iteration_index + 1,
                        }
                    )
                    return llm_reply.content
                continue

            trace_run.set_error("llm returned empty content")
            raise service_exceptions.ExternalProviderError("llm returned empty content")

    def _resolve_debounce_delay_seconds(self, tenant_id: str) -> int:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            return 0
        return agent_profile.message_debounce_delay_seconds

    def _resolve_agent_system_prompt(self, tenant_id: str) -> str:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            raise service_exceptions.ExternalProviderError(
                "agent system prompt is not configured for this tenant"
            )
        return agent_profile.system_prompt

    def _compose_base_and_runtime_system_prompt(
        self,
        base_system_prompt: str,
        runtime_prompt: str,
    ) -> str:
        return self._prompt_builder.compose_base_and_runtime_system_prompt(
            base_system_prompt=base_system_prompt,
            runtime_prompt=runtime_prompt,
        )

    def _build_runtime_system_prompt(
        self,
        runtime_context: RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
    ) -> str:
        return self._prompt_builder.build_runtime_system_prompt(
            runtime_context=runtime_context,
            known_patient=known_patient,
        )

    def _build_runtime_state_specific_instructions(
        self,
        runtime_context: RuntimePromptContext,
    ) -> list[str]:
        return self._prompt_builder.build_runtime_state_specific_instructions(runtime_context)

    def _resolve_runtime_prompt_context(
        self,
        tenant_id: str,
        conversation_id: str,
        known_patient: patient_entity.Patient | None,
    ) -> RuntimePromptContext:
        latest_open_request = self._find_latest_open_scheduling_request(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        if latest_open_request is None:
            return RuntimePromptContext(
                state="NO_ACTIVE_REQUEST",
                enabled_tool_names=self._enabled_tools_for_state("NO_ACTIVE_REQUEST"),
            )

        request_status = latest_open_request.status
        if request_status == "AWAITING_CONSULTATION_DETAILS":
            return RuntimePromptContext(
                state="AWAITING_CONSULTATION_DETAILS",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                professional_note=latest_open_request.professional_note,
                enabled_tool_names=self._enabled_tools_for_state("AWAITING_CONSULTATION_DETAILS"),
            )
        if request_status == "AWAITING_PATIENT_CHOICE":
            if latest_open_request.selected_slot_id is None:
                return RuntimePromptContext(
                    state="AWAITING_PATIENT_CHOICE",
                    request_id=latest_open_request.request_id,
                    request_status=request_status,
                    appointment_modality=latest_open_request.appointment_modality,
                    patient_location=latest_open_request.patient_location,
                    patient_preference_note=latest_open_request.patient_preference_note,
                    enabled_tool_names=self._enabled_tools_for_state("AWAITING_PATIENT_CHOICE"),
                )

            return RuntimePromptContext(
                state="COLLECTING_CONFIRMATION_DATA",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                appointment_modality=latest_open_request.appointment_modality,
                patient_location=latest_open_request.patient_location,
                patient_preference_note=latest_open_request.patient_preference_note,
                selected_slot_id=latest_open_request.selected_slot_id,
                missing_confirmation_fields=self._compute_missing_confirmation_fields(
                    request=latest_open_request,
                    known_patient=known_patient,
                ),
                enabled_tool_names=self._enabled_tools_for_state("COLLECTING_CONFIRMATION_DATA"),
            )
        if request_status == "AWAITING_PAYMENT_CONFIRMATION":
            return RuntimePromptContext(
                state="AWAITING_PAYMENT_CONFIRMATION",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                appointment_modality=latest_open_request.appointment_modality,
                selected_slot_id=latest_open_request.selected_slot_id,
                enabled_tool_names=self._enabled_tools_for_state("AWAITING_PAYMENT_CONFIRMATION"),
            )
        if request_status == "AWAITING_CONSULTATION_REVIEW":
            return RuntimePromptContext(
                state="AWAITING_CONSULTATION_REVIEW",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                professional_note=latest_open_request.professional_note,
                enabled_tool_names=self._enabled_tools_for_state("AWAITING_CONSULTATION_REVIEW"),
            )
        return RuntimePromptContext(
            state="NO_ACTIVE_REQUEST",
            enabled_tool_names=self._enabled_tools_for_state("NO_ACTIVE_REQUEST"),
        )

    def _find_latest_open_scheduling_request(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO | None:
        if self._scheduling_service is None:
            return None

        request_list = self._scheduling_service.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for request in request_list.items:
            if request.status in (
                "AWAITING_CONSULTATION_DETAILS",
                "AWAITING_CONSULTATION_REVIEW",
                "AWAITING_PATIENT_CHOICE",
                "AWAITING_PAYMENT_CONFIRMATION",
            ):
                return request
        return None

    def _enabled_tools_for_state(self, state: str) -> list[str]:
        if state in ("NO_ACTIVE_REQUEST", "AWAITING_CONSULTATION_DETAILS"):
            return [
                "submit_consultation_reason_for_review",
                "handoff_to_human",
                "cancel_active_scheduling_request",
            ]
        if state == "AWAITING_PATIENT_CHOICE":
            return [
                "handoff_to_human",
                "cancel_active_scheduling_request",
            ]
        if state == "AWAITING_PAYMENT_CONFIRMATION":
            return [
                "handoff_to_human",
                "cancel_active_scheduling_request",
            ]
        if state == "COLLECTING_CONFIRMATION_DATA":
            return [
                "confirm_selected_slot_and_create_event",
                "handoff_to_human",
                "cancel_active_scheduling_request",
            ]
        return ["handoff_to_human", "cancel_active_scheduling_request"]

    def _compute_missing_confirmation_fields(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        known_patient: patient_entity.Patient | None,
    ) -> list[str]:
        if known_patient is not None:
            return []

        missing_fields: list[str] = []

        request_full_name = self._build_patient_full_name(
            first_name=request.patient_first_name,
            last_name=request.patient_last_name,
        )
        if request_full_name is None:
            missing_fields.append("patient_full_name")
        if request.patient_age is None:
            missing_fields.append("patient_age")
        if request.consultation_reason is None:
            missing_fields.append("consultation_reason")

        requires_location = request.appointment_modality == "VIRTUAL"
        if requires_location and request.patient_location is None:
            missing_fields.append("patient_location")

        missing_fields.append("patient_email")
        if self._normalize_patient_text(request.whatsapp_user_id) is None:
            missing_fields.append("patient_phone")
        return missing_fields

    def _request_llm_reply_with_retry(
        self,
        tenant_id: str,
        conversation_id: str,
        llm_input: llm_dto.GenerateReplyInputDTO,
    ) -> llm_dto.AgentReplyDTO:
        max_attempts = len(self._llm_empty_content_retry_backoff_seconds) + 1
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
                if not self._is_llm_empty_content_error(error_message):
                    raise

                if attempt >= len(self._llm_empty_content_retry_backoff_seconds):
                    raise

                delay_seconds = self._llm_empty_content_retry_backoff_seconds[attempt]
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
                self._sleep_seconds(delay_seconds)

        raise service_exceptions.ExternalProviderError("llm returned empty content")

    def _execute_function_call(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        trace_inputs = {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "whatsapp_user_id": whatsapp_user_id,
            "function_name": function_call.name,
            "function_args": self._sanitize_trace_object(function_call.args),
        }
        with self._tracer.trace(
            name=f"webhook.function_call.{function_call.name}",
            run_type="tool",
            inputs=trace_inputs,
            tags=["webhook", "tool-call"],
        ) as trace_run:
            try:
                result: dict[str, object]
                logger.info(
                    "webhook.llm.function_call_received",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.function_call_received",
                            message="llm requested function execution",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation_id,
                                "function_name": function_call.name,
                            },
                        )
                    },
                )
                if function_call.name == "submit_consultation_reason_for_review":
                    if self._scheduling_service is None:
                        result = {"error": "scheduling service is not configured"}
                        trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                        return result
                    review_input_dto = (
                        scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO.model_validate(
                            function_call.args
                        )
                    )
                    request = self._scheduling_service.submit_consultation_reason_for_review(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        whatsapp_user_id=whatsapp_user_id,
                        input_dto=review_input_dto,
                    )
                    result = {
                        "request_id": request.request_id,
                        "status": request.status,
                        "round_number": request.round_number,
                    }
                    trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                    return result

                if function_call.name == "confirm_selected_slot_and_create_event":
                    if self._scheduling_service is None:
                        result = {"error": "scheduling service is not configured"}
                        trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                        return result
                    confirm_tool_input_dto = (
                        scheduling_dto.ConfirmSelectedSlotToolInputDTO.model_validate(
                            function_call.args
                        )
                    )
                    resolved_confirm_selection = self._resolve_confirm_selected_slot_input(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        tool_input_dto=confirm_tool_input_dto,
                    )
                    confirm_result = self._confirm_selected_slot_with_retry(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        confirm_input_dto=resolved_confirm_selection.confirm_input_dto,
                    )
                    if confirm_result.get("status") == "BOOKED":
                        self._create_patient_after_successful_booking(
                            tenant_id=tenant_id,
                            whatsapp_user_id=resolved_confirm_selection.whatsapp_user_id,
                            patient_profile=resolved_confirm_selection.patient_profile,
                            patient_exists=resolved_confirm_selection.patient_exists,
                        )
                        confirm_result["post_booking_instructions"] = (
                            self._build_post_booking_instructions(
                                appointment_modality=self._resolve_booked_modality(
                                    tenant_id=tenant_id,
                                    conversation_id=conversation_id,
                                ),
                            )
                        )
                    trace_run.set_outputs(self._summarize_tool_result_for_trace(confirm_result))
                    return confirm_result

                if function_call.name == "handoff_to_human":
                    if self._scheduling_service is None:
                        result = {"error": "scheduling service is not configured"}
                        trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                        return result
                    handoff_input_dto = scheduling_dto.HandoffToHumanInputDTO.model_validate(
                        function_call.args
                    )
                    handoff_result = self._scheduling_service.handoff_to_human(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        input_dto=handoff_input_dto,
                    )
                    result = {
                        "status": handoff_result["status"],
                        "control_mode": handoff_result["control_mode"],
                    }
                    trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                    return result

                if function_call.name == "cancel_active_scheduling_request":
                    if self._scheduling_service is None:
                        result = {"error": "scheduling service is not configured"}
                        trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                        return result
                    cancel_input_dto = (
                        scheduling_dto.CancelActiveSchedulingRequestInputDTO.model_validate(
                            function_call.args
                        )
                    )
                    cancelled_request = self._scheduling_service.cancel_active_request(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        input_dto=cancel_input_dto,
                    )
                    result = {
                        "request_id": cancelled_request.request_id,
                        "status": cancelled_request.status,
                    }
                    trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                    return result

                result = {"error": f"unknown function: {function_call.name}"}
                trace_run.set_outputs(self._summarize_tool_result_for_trace(result))
                return result
            except pydantic.ValidationError as error:
                logger.warning(
                    "webhook.llm.function_call_validation_error",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.function_call_validation_error",
                            message="function call validation failed",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation_id,
                                "function_name": function_call.name,
                                "error_message": str(error),
                            },
                        )
                    },
                )
                trace_run.set_error(str(error))
                result = {"error": str(error)}
                return result
            except service_exceptions.ServiceError as error:
                logger.warning(
                    "webhook.llm.function_call_service_error",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.function_call_service_error",
                            message="function call failed due service error",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation_id,
                                "function_name": function_call.name,
                                "error_message": str(error),
                            },
                        )
                    },
                )
                trace_run.set_error(str(error))
                result = {"error": str(error)}
                return result

    def _resolve_confirm_selected_slot_input(
        self,
        tenant_id: str,
        conversation_id: str,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
    ) -> ResolvedConfirmSelection:
        if self._scheduling_service is None:
            raise service_exceptions.InvalidStateError("scheduling service is not configured")

        request_list = self._scheduling_service.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        active_requests: list[scheduling_dto.SchedulingRequestSummaryDTO] = []
        for request in request_list.items:
            if request.status == "AWAITING_PATIENT_CHOICE":
                active_requests.append(request)

        if not active_requests:
            raise service_exceptions.InvalidStateError(
                "no scheduling request awaiting patient choice"
            )

        candidate_requests = active_requests
        if tool_input_dto.request_id is not None:
            candidate_requests = []
            for request in active_requests:
                if request.request_id == tool_input_dto.request_id:
                    candidate_requests.append(request)
            if not candidate_requests:
                raise service_exceptions.InvalidStateError(
                    "provided request_id is not awaiting patient choice"
                )

        target_request = self._select_target_request_for_confirmation(
            candidate_requests=candidate_requests,
            requested_slot_id=tool_input_dto.slot_id,
        )
        resolved_slot_id = tool_input_dto.slot_id
        if resolved_slot_id is None:
            resolved_slot_id = self._resolve_slot_id_for_confirmation(target_request)
        resolved_patient_profile, patient_exists = self._resolve_patient_profile_for_confirmation(
            tenant_id=tenant_id,
            whatsapp_user_id=target_request.whatsapp_user_id,
            request=target_request,
            tool_input_dto=tool_input_dto,
            default_patient_phone=target_request.whatsapp_user_id,
        )
        event_summary = self._build_event_summary_for_confirmation(
            resolved_patient_profile=resolved_patient_profile
        )

        return ResolvedConfirmSelection(
            confirm_input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
                request_id=target_request.request_id,
                slot_id=resolved_slot_id,
                event_summary=event_summary,
            ),
            patient_profile=resolved_patient_profile,
            patient_exists=patient_exists,
            whatsapp_user_id=target_request.whatsapp_user_id,
        )

    def _select_target_request_for_confirmation(
        self,
        candidate_requests: list[scheduling_dto.SchedulingRequestSummaryDTO],
        requested_slot_id: str | None,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        if requested_slot_id is None:
            if len(candidate_requests) == 1:
                return candidate_requests[0]
            raise service_exceptions.InvalidStateError(
                "multiple scheduling requests are waiting for confirmation"
            )

        matching_requests: list[scheduling_dto.SchedulingRequestSummaryDTO] = []
        for request in candidate_requests:
            if self._request_contains_proposed_slot(request, requested_slot_id):
                matching_requests.append(request)

        if len(matching_requests) == 1:
            return matching_requests[0]
        if len(matching_requests) > 1:
            raise service_exceptions.InvalidStateError(
                "slot_id matches multiple scheduling requests"
            )
        if len(candidate_requests) == 1:
            return candidate_requests[0]

        raise service_exceptions.InvalidStateError(
            "provided slot_id does not match active scheduling requests"
        )

    def _resolve_slot_id_for_confirmation(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str:
        if request.selected_slot_id is not None and self._request_contains_proposed_slot(
            request=request,
            slot_id=request.selected_slot_id,
        ):
            return request.selected_slot_id

        raise service_exceptions.InvalidStateError(
            "slot selection is required; ask patient to choose a slot option number"
        )

    def _enforce_required_numeric_slot_selection(
        self,
        tenant_id: str,
        conversation_id: str,
        latest_user_text: str,
    ) -> str | None:
        if self._scheduling_service is None:
            return None

        active_request = self._find_single_active_request_waiting_patient_choice(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        if active_request is None:
            return None
        if active_request.selected_slot_id is not None:
            return None

        slot_id = self._resolve_slot_id_from_option_number(
            request=active_request,
            latest_user_text=latest_user_text,
        )
        if slot_id is None:
            slot_id = self._resolve_slot_id_from_natural_language(
                request=active_request,
                latest_user_text=latest_user_text,
            )
        if slot_id is None:
            return self._build_slot_selection_retry_message(active_request)

        try:
            self._scheduling_service.select_slot_for_confirmation(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=active_request.request_id,
                slot_id=slot_id,
            )
        except service_exceptions.ServiceError:
            return self._build_slot_selection_retry_message(active_request)
        return self._build_payment_instructions_message()

    def _handle_waiting_patient_choice_state_message(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        latest_user_text: str,
    ) -> str | None:
        if self._scheduling_service is None:
            return None

        active_request = self._find_single_active_request_waiting_patient_choice(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        if active_request is None:
            return None
        if active_request.selected_slot_id is not None:
            return None

        normalized_text = latest_user_text.strip()
        if self._numeric_pattern.fullmatch(normalized_text):
            return None

        natural_language_slot_id = self._resolve_slot_id_from_natural_language(
            request=active_request,
            latest_user_text=latest_user_text,
        )
        if natural_language_slot_id is not None:
            try:
                self._scheduling_service.select_slot_for_confirmation(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    request_id=active_request.request_id,
                    slot_id=natural_language_slot_id,
                )
            except service_exceptions.ServiceError:
                return self._build_slot_selection_retry_message(active_request)
            return self._build_payment_instructions_message()

        function_calls = self._resolve_patient_choice_override_function_calls(
            latest_user_text=latest_user_text,
            active_request=active_request,
        )
        latest_assistant_text = self._find_latest_assistant_message(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for function_call in function_calls:
            if not self._should_execute_explicit_override_function(
                function_name=function_call.name,
                latest_user_text=latest_user_text,
                latest_assistant_text=latest_assistant_text,
            ):
                logger.info(
                    "webhook.patient_choice_override_ignored_non_explicit",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.patient_choice_override_ignored_non_explicit",
                            message="ignored patient choice override function because user intent was not explicit",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation_id,
                                "function_name": function_call.name,
                            },
                        )
                    },
                )
                continue
            function_response_payload = self._execute_function_call(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                function_call=function_call,
            )
            if function_call.name == "handoff_to_human":
                if function_response_payload.get("status") == "HUMAN_HANDOFF":
                    return self._build_handoff_ack_message()
                return None
            if function_call.name == "cancel_active_scheduling_request":
                if function_response_payload.get("status") == "CANCELLED":
                    return self._build_cancel_ack_message()
                return None

        patient_preference = self._detect_slot_rejection_preference(
            latest_user_text=latest_user_text,
            active_request=active_request,
        )
        if patient_preference is not None:
            return self._escalate_slot_rejection(
                tenant_id=tenant_id,
                active_request=active_request,
                patient_preference=patient_preference,
            )

        return None

    def _resolve_patient_choice_override_function_calls(
        self,
        latest_user_text: str,
        active_request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> list[llm_dto.FunctionCallDTO]:
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=self._build_patient_choice_override_system_prompt(),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=self._build_patient_choice_override_user_prompt(
                        latest_user_text=latest_user_text,
                        active_request=active_request,
                    ),
                )
            ],
            tools=self._build_tool_definitions(
                enabled_tool_names=[
                    "handoff_to_human",
                    "cancel_active_scheduling_request",
                ]
            ),
        )
        try:
            llm_reply = self._llm_provider.generate_reply(llm_input)
        except service_exceptions.ExternalProviderError:
            return []
        return llm_reply.function_calls

    def _should_execute_explicit_override_function(
        self,
        function_name: str,
        latest_user_text: str,
        latest_assistant_text: str | None,
    ) -> bool:
        if function_name == "handoff_to_human":
            return self._is_explicit_override_intent(
                latest_user_text=latest_user_text,
                latest_assistant_text=latest_assistant_text,
                target_intent="HUMAN",
            )
        if function_name == "cancel_active_scheduling_request":
            return self._is_explicit_override_intent(
                latest_user_text=latest_user_text,
                latest_assistant_text=latest_assistant_text,
                target_intent="CANCEL",
            )
        return True

    def _is_explicit_override_intent(
        self,
        latest_user_text: str,
        latest_assistant_text: str | None,
        target_intent: str,
    ) -> bool:
        previous_assistant_message = "(sin mensaje previo del asistente)"
        if latest_assistant_text is not None:
            previous_assistant_message = latest_assistant_text
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=(
                "Eres un verificador estricto de intencion explicita del paciente. "
                "Responde solo YES o NO. "
                "YES solo si el mensaje del paciente pide de forma directa la accion objetivo. "
                "Si el mensaje es un acuse breve, continuidad de la conversacion o ambiguo "
                "(por ejemplo: ok, dale, listo, gracias, perfecto, entendido), responde NO. "
                "Si hay duda, responde NO."
            ),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=(
                        f"Accion objetivo: {target_intent}\n"
                        f"Ultimo mensaje del asistente: {previous_assistant_message}\n"
                        f"Mensaje paciente: {latest_user_text}\n"
                        "Es intencion explicita?"
                    ),
                )
            ],
        )
        try:
            llm_reply = self._llm_provider.generate_reply(llm_input)
        except service_exceptions.ExternalProviderError:
            return False

        normalized_reply = (
            unicodedata.normalize(
                "NFKD",
                llm_reply.content,
            )
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        normalized_reply = normalized_reply.strip().upper()
        if not normalized_reply:
            return False
        first_token = normalized_reply.split()[0]
        return first_token in ("YES", "SI")

    def _build_patient_choice_override_system_prompt(self) -> str:
        return (
            "Estado interno: el paciente esta en AWAITING_PATIENT_CHOICE. "
            "Los horarios ya fueron propuestos y normalmente debe responder con numero. "
            "Decide si corresponde llamar una funcion: "
            "1) handoff_to_human si pide explicitamente humano, "
            "2) cancel_active_scheduling_request si pide cancelar. "
            "Si no aplica ninguna, no llames funciones."
        )

    def _build_patient_choice_override_user_prompt(
        self,
        latest_user_text: str,
        active_request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str:
        modality = active_request.appointment_modality
        if modality is None:
            modality = "PRESENCIAL"
        current_preference = active_request.patient_preference_note
        if current_preference is None:
            current_preference = ""
        location_value = active_request.patient_location
        if location_value is None:
            location_value = ""
        return (
            f"request_id_activo: {active_request.request_id}\n"
            f"modalidad_actual: {modality}\n"
            f"ubicacion_actual: {location_value}\n"
            f"preferencia_actual: {current_preference}\n"
            f"mensaje_paciente: {latest_user_text}\n"
            "Si el paciente rechaza los horarios, NO llames ninguna funcion; "
            "el profesional propondra nuevos horarios desde el panel."
        )

    def _resolve_slot_id_from_option_number(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        latest_user_text: str,
    ) -> str | None:
        normalized_text = latest_user_text.strip()
        if not self._numeric_pattern.fullmatch(normalized_text):
            return None
        option_number = str(int(normalized_text))
        selected_slot_id = request.slot_options_map.get(option_number)
        if selected_slot_id is None:
            return None
        if not self._request_contains_proposed_slot(request=request, slot_id=selected_slot_id):
            return None
        return selected_slot_id

    def _resolve_slot_id_from_natural_language(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        latest_user_text: str,
    ) -> str | None:
        slot_by_id: dict[str, scheduling_dto.SchedulingSlotDTO] = {}
        for slot in request.slots:
            slot_by_id[slot.slot_id] = slot

        option_lines: list[str] = []
        for option_number in sorted(request.slot_options_map.keys(), key=int):
            slot_id = request.slot_options_map[option_number]
            slot_candidate = slot_by_id.get(slot_id)
            if slot_candidate is None:
                continue
            if slot_candidate.status not in ("PROPOSED", "SELECTED"):
                continue
            option_lines.append(
                scheduling_slot_formatter.format_slot_option_line(
                    option_number=option_number,
                    start_at=slot_candidate.start_at,
                    timezone_name=slot_candidate.timezone,
                )
            )
        if not option_lines:
            return None

        options_block = "\n".join(option_lines)
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=(
                "Eres un asistente que mapea la respuesta del paciente a una opcion de horario. "
                "Responde UNICAMENTE con el numero de opcion que corresponde al mensaje del paciente. "
                "Si el paciente menciona una fecha, dia u hora que coincida con una de las opciones, "
                "responde con el numero de esa opcion. "
                "Si el mensaje no coincide con ninguna opcion o es ambiguo, responde NINGUNA."
            ),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=(
                        f"Opciones disponibles:\n{options_block}\n\n"
                        f"Mensaje del paciente: {latest_user_text}\n\n"
                        "Numero de opcion elegida (o NINGUNA):"
                    ),
                )
            ],
        )
        try:
            llm_reply = self._llm_provider.generate_reply(llm_input)
        except service_exceptions.ExternalProviderError:
            return None

        resolved_text = llm_reply.content.strip()
        if not self._numeric_pattern.fullmatch(resolved_text):
            return None
        option_number = str(int(resolved_text))
        selected_slot_id = request.slot_options_map.get(option_number)
        if selected_slot_id is None:
            return None
        if not self._request_contains_proposed_slot(request=request, slot_id=selected_slot_id):
            return None
        return selected_slot_id

    def _detect_slot_rejection_preference(
        self,
        latest_user_text: str,
        active_request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str | None:
        slot_by_id: dict[str, scheduling_dto.SchedulingSlotDTO] = {}
        for slot in active_request.slots:
            slot_by_id[slot.slot_id] = slot

        option_lines: list[str] = []
        for option_number in sorted(active_request.slot_options_map.keys(), key=int):
            slot_id = active_request.slot_options_map[option_number]
            slot_candidate = slot_by_id.get(slot_id)
            if slot_candidate is None:
                continue
            if slot_candidate.status not in ("PROPOSED", "SELECTED"):
                continue
            option_lines.append(
                scheduling_slot_formatter.format_slot_option_line(
                    option_number=option_number,
                    start_at=slot_candidate.start_at,
                    timezone_name=slot_candidate.timezone,
                )
            )
        if not option_lines:
            return None

        options_block = "\n".join(option_lines)
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=(
                "Eres un asistente que analiza si el paciente esta rechazando los horarios propuestos "
                "y expresando una preferencia de horario diferente. "
                "Si el paciente indica que ninguno de los horarios le sirve, o dice que no puede en esos dias/horas "
                "y sugiere otros dias u horas, responde con un resumen breve de la preferencia del paciente "
                "(por ejemplo: 'Prefiere miercoles en la tarde' o 'No puede martes, prefiere otro dia'). "
                "Si el paciente esta intentando elegir uno de los horarios propuestos, preguntando algo, "
                "o su mensaje no es un rechazo claro de los horarios, responde NINGUNA."
            ),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=(
                        f"Horarios propuestos:\n{options_block}\n\n"
                        f"Mensaje del paciente: {latest_user_text}\n\n"
                        "Preferencia del paciente (o NINGUNA):"
                    ),
                )
            ],
        )
        try:
            llm_reply = self._llm_provider.generate_reply(llm_input)
        except service_exceptions.ExternalProviderError:
            return None

        resolved_text = llm_reply.content.strip()
        if not resolved_text:
            return None
        normalized_upper = resolved_text.upper()
        if normalized_upper == "NINGUNA" or normalized_upper.startswith("NINGUNA"):
            return None
        return resolved_text

    def _escalate_slot_rejection(
        self,
        tenant_id: str,
        active_request: scheduling_dto.SchedulingRequestSummaryDTO,
        patient_preference: str,
    ) -> str:
        if self._scheduling_service is None:
            return self._build_slot_rejection_ack_message()

        try:
            self._scheduling_service.escalate_patient_slot_rejection(
                tenant_id=tenant_id,
                request_id=active_request.request_id,
                patient_preference_note=patient_preference,
            )
        except service_exceptions.ServiceError:
            logger.warning(
                "webhook.slot_rejection_escalation_failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.slot_rejection_escalation_failed",
                        message="failed to escalate patient slot rejection",
                        data={
                            "tenant_id": tenant_id,
                            "request_id": active_request.request_id,
                        },
                    )
                },
            )
        return self._build_slot_rejection_ack_message()

    def _build_slot_rejection_ack_message(self) -> str:
        return (
            "Entendido, voy a consultar otros horarios disponibles. "
            "Te aviso apenas tenga nuevas opciones."
        )

    def _build_slot_selection_retry_message(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str:
        slot_by_id: dict[str, scheduling_dto.SchedulingSlotDTO] = {}
        for slot in request.slots:
            slot_by_id[slot.slot_id] = slot

        lines = ["Para continuar, elige un horario respondiendo solo con el numero de opcion."]
        for option_number in sorted(request.slot_options_map.keys(), key=int):
            slot_id = request.slot_options_map[option_number]
            slot_candidate = slot_by_id.get(slot_id)
            if slot_candidate is None:
                continue
            if slot_candidate.status not in ("PROPOSED", "SELECTED"):
                continue
            lines.append(
                scheduling_slot_formatter.format_slot_option_line(
                    option_number=option_number,
                    start_at=slot_candidate.start_at,
                    timezone_name=slot_candidate.timezone,
                )
            )
        lines.append("Ejemplo: 2")
        return "\n".join(lines)

    def _handle_waiting_professional_state_message(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        latest_user_text: str,
    ) -> str | None:
        waiting_request = self._find_latest_waiting_professional_request(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        if waiting_request is None:
            return None

        waiting_override_function_calls = self._resolve_waiting_state_override_function_calls(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            latest_user_text=latest_user_text,
            waiting_request_status=waiting_request.status,
        )
        if not waiting_override_function_calls:
            return None

        latest_assistant_text = self._find_latest_assistant_message(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for function_call in waiting_override_function_calls:
            if not self._should_execute_explicit_override_function(
                function_name=function_call.name,
                latest_user_text=latest_user_text,
                latest_assistant_text=latest_assistant_text,
            ):
                logger.info(
                    "webhook.waiting_override_ignored_non_explicit",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.waiting_override_ignored_non_explicit",
                            message="ignored waiting override function because user intent was not explicit",
                            data={
                                "tenant_id": tenant_id,
                                "conversation_id": conversation_id,
                                "function_name": function_call.name,
                            },
                        )
                    },
                )
                continue
            function_response_payload = self._execute_function_call(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                function_call=function_call,
            )
            if function_call.name == "handoff_to_human":
                if function_response_payload.get("status") == "HUMAN_HANDOFF":
                    return self._build_handoff_ack_message()
                return None
            if function_call.name == "cancel_active_scheduling_request":
                if function_response_payload.get("status") == "CANCELLED":
                    return self._build_cancel_ack_message()
                return None
        return None

    def _find_latest_assistant_message(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> str | None:
        history_messages = self._conversation_repository.list_messages(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for message in reversed(history_messages):
            if message.role == "user":
                continue
            normalized_content = message.content.strip()
            if not normalized_content:
                continue
            return normalized_content
        return None

    def _resolve_waiting_state_override_function_calls(
        self,
        tenant_id: str,
        conversation_id: str,
        latest_user_text: str,
        waiting_request_status: str,
    ) -> list[llm_dto.FunctionCallDTO]:
        del tenant_id
        del conversation_id
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=self._build_waiting_state_system_prompt(),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=self._build_waiting_state_user_prompt(
                        latest_user_text=latest_user_text,
                        waiting_request_status=waiting_request_status,
                    ),
                )
            ],
            tools=self._build_waiting_state_tool_definitions(),
        )
        try:
            llm_reply = self._llm_provider.generate_reply(llm_input)
        except service_exceptions.ExternalProviderError:
            return []
        return llm_reply.function_calls

    def _build_waiting_state_system_prompt(self) -> str:
        return (
            "Clasifica si el paciente pidio explicitamente: "
            "1) hablar con un humano, o 2) cancelar el proceso actual. "
            "Si no hay una peticion explicita de humano o cancelacion, no llames ninguna funcion y responde vacio. "
            "No llames otras funciones."
        )

    def _build_waiting_state_user_prompt(
        self,
        latest_user_text: str,
        waiting_request_status: str,
    ) -> str:
        return (
            f"Estado actual interno: {waiting_request_status}\\n"
            f"Mensaje del paciente: {latest_user_text}\\n"
            "Si pide explicitamente humano, llama handoff_to_human. "
            "Si pide explicitamente cancelar, llama cancel_active_scheduling_request."
        )

    def _build_handoff_ack_message(self) -> str:
        return "Claro, te comunico con una persona de nuestro equipo."

    def _build_cancel_ack_message(self) -> str:
        return "Listo, cancelé este proceso. Si quieres retomarlo más adelante, te ayudo por aquí."

    def _build_reason_review_ack_message(self) -> str:
        return "Gracias por compartir la información. Dame un momento y te ayudo a continuar."

    def _build_availability_ack_message(self) -> str:
        return "Perfecto. Dame un momento y te comparto opciones de horario."

    def _build_payment_instructions_message(self) -> str:
        return (
            "Para continuar con el proceso de agendamiento, realiza la transferencia:\n"
            "• Nequi: 318 732 6409\n"
            "• A nombre de: Alejandra Escobar\n\n"
            "Una vez realizado el pago, envíame el comprobante."
        )

    def _build_post_booking_instructions(
        self,
        appointment_modality: str | None,
    ) -> str:
        if appointment_modality == "PRESENCIAL":
            return (
                "Informacion y recomendaciones:\n"
                "• Direccion: Calle 13 #78 54, edificio centro ejecutivo, "
                "oficina 409 (al lado de San Andresito del sur).\n"
                "• Presentar documento de identidad para el ingreso.\n"
                "• Llegar con 20 minutos de antelacion y encontrar parqueadero.\n"
                "• Reprogramaciones con 24 horas de antelacion."
            )
        return (
            "Informacion y recomendaciones:\n"
            "• Te enviaremos el link de la sesion antes de la cita.\n"
            "• Reprogramaciones con 24 horas de antelacion."
        )

    def _resolve_booked_modality(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> str | None:
        if self._scheduling_service is None:
            return None
        request_list = self._scheduling_service.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for request in request_list.items:
            if request.status == "BOOKED":
                return request.appointment_modality
        return None

    def _find_latest_waiting_professional_request(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO | None:
        if self._scheduling_service is None:
            return None

        request_list = self._scheduling_service.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for request in request_list.items:
            if request.status in (
                "AWAITING_CONSULTATION_REVIEW",
                "AWAITING_PAYMENT_CONFIRMATION",
            ):
                return request
        return None

    def _is_waiting_professional_state_active(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> bool:
        return (
            self._find_latest_waiting_professional_request(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            )
            is not None
        )

    def _find_single_active_request_waiting_patient_choice(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO | None:
        if self._scheduling_service is None:
            return None

        request_list = self._scheduling_service.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        active_requests: list[scheduling_dto.SchedulingRequestSummaryDTO] = []
        for request in request_list.items:
            if request.status == "AWAITING_PATIENT_CHOICE":
                active_requests.append(request)

        if len(active_requests) != 1:
            return None
        return active_requests[0]

    def _resolve_patient_profile_for_confirmation(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
        default_patient_phone: str | None,
    ) -> tuple[ResolvedPatientProfile, bool]:
        existing_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
        )
        if existing_patient is not None:
            self._log_existing_patient_mismatch(
                tenant_id=tenant_id,
                whatsapp_user_id=whatsapp_user_id,
                existing_patient=existing_patient,
                tool_input_dto=tool_input_dto,
            )
            return (
                ResolvedPatientProfile(
                    full_name=self._build_patient_full_name(
                        first_name=existing_patient.first_name,
                        last_name=existing_patient.last_name,
                    )
                    or existing_patient.first_name,
                    email=existing_patient.email,
                    age=existing_patient.age,
                    consultation_reason=existing_patient.consultation_reason,
                    location=existing_patient.location,
                    phone=existing_patient.phone,
                ),
                True,
            )

        patient_full_name = self._coalesce_patient_text(
            primary=tool_input_dto.patient_full_name,
            fallback=self._build_patient_full_name(
                first_name=self._coalesce_patient_text(
                    primary=request.patient_first_name,
                    fallback=tool_input_dto.patient_first_name,
                ),
                last_name=self._coalesce_patient_text(
                    primary=request.patient_last_name,
                    fallback=tool_input_dto.patient_last_name,
                ),
            ),
        )
        if patient_full_name is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_full_name; ask only for the patient's full name now"
            )

        patient_email = self._normalize_patient_text(tool_input_dto.patient_email)
        if patient_email is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_email; ask only for the patient's email now"
            )
        if not self._email_pattern.fullmatch(patient_email):
            raise service_exceptions.InvalidStateError(
                "patient_email is invalid; ask only for a valid email now"
            )

        patient_phone = self._resolve_patient_phone(
            provided_patient_phone=tool_input_dto.patient_phone,
            fallback_patient_phone=default_patient_phone,
        )
        if patient_phone is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_phone; ask only for the patient's phone number now"
            )

        patient_age = self._coalesce_patient_age(
            primary=request.patient_age,
            fallback=tool_input_dto.patient_age,
        )
        if patient_age is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_age; ask only for the patient's age now"
            )
        if patient_age < 1 or patient_age > 120:
            raise service_exceptions.InvalidStateError(
                "patient_age is invalid; ask only for age as a whole number between 1 and 120"
            )

        consultation_reason = self._coalesce_patient_text(
            primary=request.consultation_reason,
            fallback=tool_input_dto.consultation_reason,
        )
        if consultation_reason is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: consultation_reason; ask only for the consultation reason now"
            )

        patient_location = self._coalesce_patient_text(
            primary=request.patient_location,
            fallback=tool_input_dto.patient_location,
        )
        if patient_location is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_location; ask only for the patient's location now"
            )

        return (
            ResolvedPatientProfile(
                full_name=patient_full_name,
                email=patient_email,
                age=patient_age,
                consultation_reason=consultation_reason,
                location=patient_location,
                phone=patient_phone,
            ),
            False,
        )

    def _build_event_summary_for_confirmation(
        self,
        resolved_patient_profile: ResolvedPatientProfile,
    ) -> str:
        return f"{resolved_patient_profile.full_name}/ {self._professional_signature}"

    def _log_existing_patient_mismatch(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        existing_patient: patient_entity.Patient,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
    ) -> None:
        mismatched_fields: list[str] = []
        existing_full_name = self._build_patient_full_name(
            first_name=existing_patient.first_name,
            last_name=existing_patient.last_name,
        )

        normalized_full_name = self._normalize_patient_text(tool_input_dto.patient_full_name)
        if normalized_full_name is not None and normalized_full_name != existing_full_name:
            mismatched_fields.append("patient_full_name")

        normalized_first_name = self._normalize_patient_text(tool_input_dto.patient_first_name)
        if (
            normalized_first_name is not None
            and normalized_first_name != existing_patient.first_name
        ):
            mismatched_fields.append("patient_first_name")

        normalized_last_name = self._normalize_patient_text(tool_input_dto.patient_last_name)
        if normalized_last_name is not None and normalized_last_name != existing_patient.last_name:
            mismatched_fields.append("patient_last_name")

        normalized_email = self._normalize_patient_text(tool_input_dto.patient_email)
        if normalized_email is not None and normalized_email != existing_patient.email:
            mismatched_fields.append("patient_email")

        normalized_phone = self._normalize_patient_text(tool_input_dto.patient_phone)
        if normalized_phone is not None and normalized_phone != existing_patient.phone:
            mismatched_fields.append("patient_phone")

        normalized_age = self._normalize_patient_age(tool_input_dto.patient_age)
        if normalized_age is not None and normalized_age != existing_patient.age:
            mismatched_fields.append("patient_age")

        normalized_reason = self._normalize_patient_text(tool_input_dto.consultation_reason)
        if (
            normalized_reason is not None
            and normalized_reason != existing_patient.consultation_reason
        ):
            mismatched_fields.append("consultation_reason")

        normalized_location = self._normalize_patient_text(tool_input_dto.patient_location)
        if normalized_location is not None and normalized_location != existing_patient.location:
            mismatched_fields.append("patient_location")

        if not mismatched_fields:
            return

        logger.info(
            "webhook.patient.mismatch_ignored",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.patient.mismatch_ignored",
                    message="incoming patient data differs from stored profile; stored profile is kept",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": whatsapp_user_id,
                        "mismatched_fields": sorted(set(mismatched_fields)),
                    },
                )
            },
        )

    def _create_patient_after_successful_booking(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        patient_profile: ResolvedPatientProfile,
        patient_exists: bool,
    ) -> None:
        if patient_exists:
            return

        existing_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
        )
        if existing_patient is not None:
            return

        patient = patient_entity.Patient(
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
            first_name=self._extract_first_name(patient_profile.full_name),
            last_name=self._extract_last_name(patient_profile.full_name),
            email=patient_profile.email,
            age=patient_profile.age,
            consultation_reason=patient_profile.consultation_reason,
            location=patient_profile.location,
            phone=patient_profile.phone,
            created_at=self._clock.now(),
        )
        self._patient_repository.save(patient)
        logger.info(
            "webhook.patient.created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.patient.created",
                    message="patient record created after booking confirmation",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": whatsapp_user_id,
                    },
                )
            },
        )

    def _coalesce_patient_text(self, primary: str | None, fallback: str | None) -> str | None:
        normalized_primary = self._normalize_patient_text(primary)
        if normalized_primary is not None:
            return normalized_primary
        return self._normalize_patient_text(fallback)

    def _coalesce_patient_age(
        self,
        primary: int | None,
        fallback: int | str | None,
    ) -> int | None:
        if primary is not None:
            return primary
        return self._normalize_patient_age(fallback)

    def _normalize_patient_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        return normalized_value

    def _build_patient_full_name(
        self,
        first_name: str | None,
        last_name: str | None,
    ) -> str | None:
        normalized_first_name = self._normalize_patient_text(first_name)
        normalized_last_name = self._normalize_patient_text(last_name)
        if normalized_first_name is None and normalized_last_name is None:
            return None
        if normalized_first_name is None:
            return normalized_last_name
        if normalized_last_name is None:
            return normalized_first_name
        return f"{normalized_first_name} {normalized_last_name}"

    def _extract_first_name(self, full_name: str) -> str:
        normalized_full_name = full_name.strip()
        parts = normalized_full_name.split()
        if not parts:
            return normalized_full_name
        return parts[0]

    def _extract_last_name(self, full_name: str) -> str:
        normalized_full_name = full_name.strip()
        parts = normalized_full_name.split()
        if len(parts) <= 1:
            return normalized_full_name
        return " ".join(parts[1:])

    def _normalize_patient_age(self, value: int | str | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        if not normalized_value.isdigit():
            return None
        return int(normalized_value)

    def _resolve_patient_phone(
        self,
        provided_patient_phone: str | None,
        fallback_patient_phone: str | None,
    ) -> str | None:
        normalized_provided_phone = self._normalize_patient_text(provided_patient_phone)
        if normalized_provided_phone is not None:
            return normalized_provided_phone
        return self._normalize_patient_text(fallback_patient_phone)

    def _request_contains_proposed_slot(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        slot_id: str,
    ) -> bool:
        return any(
            slot.slot_id == slot_id and slot.status in ("PROPOSED", "SELECTED")
            for slot in request.slots
        )

    def _confirm_selected_slot_with_retry(
        self,
        tenant_id: str,
        conversation_id: str,
        confirm_input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO,
    ) -> dict[str, object]:
        if self._scheduling_service is None:
            return {"error": "scheduling service is not configured"}

        max_attempts = len(self._google_network_retry_backoff_seconds) + 1
        for attempt in range(max_attempts):
            try:
                result = self._scheduling_service.confirm_selected_slot_and_create_event(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    input_dto=confirm_input_dto,
                )
                return result.model_dump(mode="json")
            except service_exceptions.ExternalProviderError as error:
                error_message = str(error)
                if self._is_google_network_error(error_message):
                    if attempt < len(self._google_network_retry_backoff_seconds):
                        delay_seconds = self._google_network_retry_backoff_seconds[attempt]
                        logger.warning(
                            "webhook.scheduling.retry_google_network_error",
                            extra={
                                "event_data": app_logs.build_log_event(
                                    event_name="webhook.scheduling.retry_google_network_error",
                                    message="retrying google calendar error while confirming slot",
                                    data={
                                        "tenant_id": tenant_id,
                                        "conversation_id": conversation_id,
                                        "request_id": confirm_input_dto.request_id,
                                        "slot_id": confirm_input_dto.slot_id,
                                        "attempt": attempt + 1,
                                        "delay_seconds": delay_seconds,
                                    },
                                )
                            },
                        )
                        self._sleep_seconds(delay_seconds)
                        continue
                    return self._handoff_due_to_google_error(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        request_id=confirm_input_dto.request_id,
                        slot_id=confirm_input_dto.slot_id,
                        reason="google_network_error",
                        error_message=error_message,
                    )

                return self._handoff_due_to_google_error(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    request_id=confirm_input_dto.request_id,
                    slot_id=confirm_input_dto.slot_id,
                    reason="google_unknown_error",
                    error_message=error_message,
                )

        return self._handoff_due_to_google_error(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=confirm_input_dto.request_id,
            slot_id=confirm_input_dto.slot_id,
            reason="google_network_error",
            error_message="retry loop exhausted",
        )

    def _handoff_due_to_google_error(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        slot_id: str,
        reason: str,
        error_message: str,
    ) -> dict[str, object]:
        if self._scheduling_service is None:
            return {
                "status": "HUMAN_HANDOFF",
                "control_mode": "HUMAN",
                "reason": reason,
                "error": error_message,
            }

        summary_for_professional = (
            "No se pudo confirmar el horario con Google Calendar. "
            f"request_id={request_id} slot_id={slot_id} error={error_message}"
        )
        handoff_result = self._scheduling_service.handoff_to_human(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            input_dto=scheduling_dto.HandoffToHumanInputDTO(
                reason=reason,
                summary_for_professional=summary_for_professional,
            ),
        )
        return {
            "status": handoff_result["status"],
            "control_mode": handoff_result["control_mode"],
            "reason": reason,
        }

    def _is_google_network_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "network error" in normalized_message or "timeout" in normalized_message

    def _is_llm_empty_content_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "empty content" in normalized_message

    def _build_waiting_state_tool_definitions(self) -> list[llm_dto.FunctionDeclarationDTO]:
        return self._tool_registry.build_waiting_state_tool_definitions()

    def _build_tool_definitions(
        self,
        enabled_tool_names: list[str] | None = None,
    ) -> list[llm_dto.FunctionDeclarationDTO]:
        return self._tool_registry.build_tool_definitions(enabled_tool_names=enabled_tool_names)

    def _conversation_has_provider_message_id(
        self,
        conversation: conversation_entity.Conversation,
        provider_message_id: str,
    ) -> bool:
        for message in conversation.messages:
            if message.provider_message_id == provider_message_id:
                return True
        for subsession in conversation.subsessions:
            for message in subsession.messages:
                if message.provider_message_id == provider_message_id:
                    return True
        return False

    def _summarize_tool_result_for_trace(
        self, result: typing.Mapping[str, object]
    ) -> dict[str, object]:
        summary: dict[str, object] = {
            "has_error": "error" in result,
        }
        status = result.get("status")
        if isinstance(status, str):
            summary["status"] = status
        request_id = result.get("request_id")
        if isinstance(request_id, str):
            summary["request_id"] = request_id
        control_mode = result.get("control_mode")
        if isinstance(control_mode, str):
            summary["control_mode"] = control_mode
        return summary

    def _sanitize_trace_text(self, value: str, *, max_chars: int = 180) -> str:
        sanitized_value = value
        sanitized_value = self._trace_email_pattern.sub("[redacted-email]", sanitized_value)
        sanitized_value = self._trace_phone_pattern.sub("[redacted-phone]", sanitized_value)
        if len(sanitized_value) > max_chars:
            return f"{sanitized_value[:max_chars]}..."
        return sanitized_value

    def _sanitize_trace_object(self, value: object) -> object:
        if isinstance(value, str):
            return self._sanitize_trace_text(value)
        if isinstance(value, int | float | bool):
            return value
        if value is None:
            return None
        if isinstance(value, list):
            sanitized_items: list[object] = []
            for item in value:
                sanitized_items.append(self._sanitize_trace_object(item))
            return sanitized_items
        if isinstance(value, dict):
            sanitized_dict: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    continue
                lowered_key = key.lower()
                if "email" in lowered_key:
                    sanitized_dict[key] = "[redacted-email]"
                    continue
                if "phone" in lowered_key:
                    sanitized_dict[key] = "[redacted-phone]"
                    continue
                sanitized_dict[key] = self._sanitize_trace_object(item)
            return sanitized_dict
        return str(value)

    def _mark_event_processed(self, tenant_id: str, provider_event_id: str) -> None:
        self._processed_webhook_event_repository.mark_processed(
            tenant_id=tenant_id,
            provider_event_id=provider_event_id,
            processed_at=self._clock.now(),
        )

    def _mark_event_failed_by_phone_number(
        self,
        phone_number_id: str,
        provider_event_id: str,
        failure_reason: str,
    ) -> None:
        connection = self._whatsapp_connection_repository.get_by_phone_number_id(phone_number_id)
        if connection is None:
            return
        tenant_id = connection.tenant_id
        if not self._processed_webhook_event_repository.exists(tenant_id, provider_event_id):
            return
        try:
            self._processed_webhook_event_repository.mark_failed(
                tenant_id=tenant_id,
                provider_event_id=provider_event_id,
                failed_at=self._clock.now(),
                failure_reason=self._truncate_failure_reason(failure_reason),
            )
        except Exception:
            logger.warning(
                "webhook.event_failed_mark_error",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.event_failed_mark_error",
                        message="failed to persist failed status for webhook event",
                        data={
                            "tenant_id": tenant_id,
                            "provider_event_id": provider_event_id,
                        },
                    )
                },
            )

    def _truncate_failure_reason(self, failure_reason: str) -> str:
        normalized_reason = failure_reason.strip()
        if normalized_reason == "":
            return "unknown webhook processing error"
        if len(normalized_reason) <= 280:
            return normalized_reason
        return f"{normalized_reason[:280]}..."
