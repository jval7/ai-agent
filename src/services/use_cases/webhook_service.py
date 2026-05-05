import re
import time
import typing

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.infra.langsmith_tracer as langsmith_tracer
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.agent_workflow_port as agent_workflow_port
import src.ports.blacklist_repository_port as blacklist_repository_port
import src.ports.clock_port as clock_port
import src.ports.conversation_processing_lock_port as conversation_processing_lock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.agentic.conversation_message_sender as conversation_message_sender_mod
import src.services.agentic.guards.waiting_professional_silent_guard as professional_silent_guard_mod
import src.services.agentic.prompt_builder as prompt_builder
import src.services.agentic.runtime_context_resolver as runtime_context_resolver_mod
import src.services.agentic.tool_calling_orchestrator as tool_calling_orchestrator_mod
import src.services.agentic.workflow_engine as workflow_engine
import src.services.agentic.workflow_runtime_adapter as workflow_runtime_adapter_mod
import src.services.dto.agent_workflow_dto as agent_workflow_dto
import src.services.dto.llm_dto as llm_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.conversation_provisioning as conversation_provisioning
import src.services.use_cases.scheduling_service as scheduling_service_mod

logger = app_logs.get_logger(__name__)


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
        scheduling_service: scheduling_service_mod.SchedulingService | None,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        context_message_limit: int,
        tool_calling_orchestrator: tool_calling_orchestrator_mod.ToolCallingOrchestrator,
        runtime_context_resolver: runtime_context_resolver_mod.RuntimeContextResolver,
        message_sender: conversation_message_sender_mod.ConversationMessageSender,
        tracer: langsmith_tracer.LangsmithTracer | None = None,
        sleep_seconds: typing.Callable[[float], None] | None = None,
        agent_workflow: agent_workflow_port.AgentWorkflowPort | None = None,
        runtime_prompt_builder: prompt_builder.RuntimePromptBuilder | None = None,
        conversation_processing_lock: conversation_processing_lock_port.ConversationProcessingLockPort
        | None = None,
        professional_silent_guard: professional_silent_guard_mod.WaitingProfessionalSilentGuard
        | None = None,
    ) -> None:
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._conversation_repository = conversation_repository
        self._patient_repository = patient_repository
        self._processed_webhook_event_repository = processed_webhook_event_repository
        self._blacklist_repository = blacklist_repository
        self._agent_profile_repository = agent_profile_repository
        self._conversation_processing_lock = conversation_processing_lock
        self._whatsapp_provider = whatsapp_provider
        self._id_generator = id_generator
        self._clock = clock
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
        if tracer is None:
            self._tracer = langsmith_tracer.LangsmithTracer()
        else:
            self._tracer = tracer
        self._max_debounce_reprocess_iterations = 3
        self._trace_email_pattern = re.compile(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
        )
        self._trace_phone_pattern = re.compile(r"\+?\d{7,15}")
        self._professional_silent_guard = professional_silent_guard
        self._tool_calling_orchestrator = tool_calling_orchestrator
        self._runtime_context_resolver = runtime_context_resolver
        self._message_sender = message_sender
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
        _whatsapp_user, conversation = (
            conversation_provisioning.ensure_conversation_for_whatsapp_user(
                tenant_id=tenant_id,
                whatsapp_user_id=event.whatsapp_user_id,
                display_name=event.whatsapp_user_name,
                now_value=now_value,
                conversation_repository=self._conversation_repository,
                id_generator=self._id_generator,
            )
        )

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

        if event.source == "PROFESSIONAL_APP":
            professional_message = message_entity.Message(
                id=self._id_generator.new_id(),
                conversation_id=conversation.id,
                tenant_id=tenant_id,
                direction="OUTBOUND",
                role="human_agent",
                content=event.message_text,
                provider_message_id=event.message_id,
                created_at=now_value,
            )
            self._conversation_repository.save_message(professional_message)
            conversation.append_message(
                professional_message.id,
                professional_message.content,
                professional_message.created_at,
            )
            conversation.set_control_mode("HUMAN", professional_message.created_at)
            self._conversation_repository.save_conversation(conversation)
            self._mark_event_processed(tenant_id, event.provider_event_id)
            logger.info(
                "webhook.professional_handoff_human",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.professional_handoff_human",
                        message="professional app message moved conversation to HUMAN mode",
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

        if not self._is_assistant_enabled(tenant_id):
            self._mark_event_processed(tenant_id, event.provider_event_id)
            logger.info(
                "webhook.assistant_disabled_skip_ai",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.assistant_disabled_skip_ai",
                        message="customer message persisted while assistant is globally disabled for tenant",
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
                    runtime_adapter = (
                        workflow_runtime_adapter_mod.WebhookConversationWorkflowRuntimeAdapter(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            whatsapp_user_id=event.whatsapp_user_id,
                            latest_user_text=latest_user_text,
                            llm_messages=llm_messages,
                            known_patient=known_patient,
                            runtime_context_resolver=self._runtime_context_resolver,
                            prompt_builder_instance=self._prompt_builder,
                            agent_profile_repository=self._agent_profile_repository,
                            tool_calling_orchestrator=self._tool_calling_orchestrator,
                            professional_silent_guard=self._professional_silent_guard,
                        )
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

                    outbound_message_provider_id = self._message_sender.send_assistant_message(
                        connection=connection,
                        conversation_id=conversation.id,
                        tenant_id=tenant_id,
                        whatsapp_user_id=event.whatsapp_user_id,
                        text=workflow_result.text,
                    )
                    if workflow_result.reason == "AI_REPLY":
                        self._message_sender.archive_messages_into_subsession_if_booking_occurred(
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
                        self._message_sender.send_assistant_message(
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
        reason_events: dict[str, tuple[str, str]] = {
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
        event_name, log_message = reason_events.get(
            workflow_reason, ("webhook.ai_reply_sent", "ai reply sent and persisted")
        )
        data: dict[str, object] = {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "provider_event_id": provider_event_id,
        }
        if event_name == "webhook.ai_reply_sent":
            data["outbound_provider_message_id"] = outbound_message_provider_id
        logger.info(
            event_name,
            extra={
                "event_data": app_logs.build_log_event(
                    event_name=event_name, message=log_message, data=data
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

    def _resolve_debounce_delay_seconds(self, tenant_id: str) -> int:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            return 0
        return agent_profile.message_debounce_delay_seconds

    def _is_assistant_enabled(self, tenant_id: str) -> bool:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            return True
        return agent_profile.assistant_enabled

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

    def _sanitize_trace_text(self, value: str, *, max_chars: int = 180) -> str:
        sanitized_value = value
        sanitized_value = self._trace_email_pattern.sub("[redacted-email]", sanitized_value)
        sanitized_value = self._trace_phone_pattern.sub("[redacted-phone]", sanitized_value)
        if len(sanitized_value) > max_chars:
            return f"{sanitized_value[:max_chars]}..."
        return sanitized_value

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
        except service_exceptions.ExternalProviderError as error:
            logger.warning(
                "webhook.event_failed_mark_error",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="webhook.event_failed_mark_error",
                        message="failed to persist failed status for webhook event",
                        data={
                            "tenant_id": tenant_id,
                            "provider_event_id": provider_event_id,
                            "error": str(error),
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
        return f"{normalized_reason[:277]}..."
