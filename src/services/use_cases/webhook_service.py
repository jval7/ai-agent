import time
import typing

import pydantic

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.processed_webhook_event as processed_webhook_event_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.blacklist_repository_port as blacklist_repository_port
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.llm_provider_port as llm_provider_port
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class WebhookService:
    def __init__(
        self,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
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
        sleep_seconds: typing.Callable[[float], None] | None = None,
    ) -> None:
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._conversation_repository = conversation_repository
        self._processed_webhook_event_repository = processed_webhook_event_repository
        self._blacklist_repository = blacklist_repository
        self._agent_profile_repository = agent_profile_repository
        self._scheduling_service = scheduling_service
        self._llm_provider = llm_provider
        self._whatsapp_provider = whatsapp_provider
        self._id_generator = id_generator
        self._clock = clock
        self._default_system_prompt = default_system_prompt
        self._context_message_limit = context_message_limit
        self._max_function_call_iterations = 4
        self._google_network_retry_backoff_seconds = [1.0, 2.0, 4.0]
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
            self._process_event(event)
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
        if self._processed_webhook_event_repository.exists(tenant_id, event.provider_event_id):
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

        history = self._conversation_repository.list_messages(tenant_id, conversation.id)
        history_messages = history[-self._context_message_limit :]
        llm_messages: list[llm_dto.ChatMessageDTO] = []
        for message in history_messages:
            message_role = message.role
            if message_role == "human_agent":
                message_role = "assistant"
            llm_messages.append(llm_dto.ChatMessageDTO(role=message_role, content=message.content))

        try:
            assistant_text = self._generate_reply_with_tools(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                whatsapp_user_id=event.whatsapp_user_id,
                llm_messages=llm_messages,
            )
            outbound_message_provider_id = self._whatsapp_provider.send_text_message(
                access_token=connection.access_token,
                phone_number_id=connection.phone_number_id,
                whatsapp_user_id=event.whatsapp_user_id,
                text=assistant_text,
            )
        except service_exceptions.ExternalProviderError as error:
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
            raise

        outbound_message = message_entity.Message(
            id=self._id_generator.new_id(),
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            direction="OUTBOUND",
            role="assistant",
            content=assistant_text,
            provider_message_id=outbound_message_provider_id,
            created_at=self._clock.now(),
        )
        self._conversation_repository.save_message(outbound_message)
        latest_conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation.id
        )
        if latest_conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")
        latest_conversation.append_message(
            outbound_message.id,
            outbound_message.content,
            outbound_message.created_at,
        )
        self._conversation_repository.save_conversation(latest_conversation)

        self._mark_event_processed(tenant_id, event.provider_event_id)
        logger.info(
            "webhook.ai_reply_sent",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.ai_reply_sent",
                    message="ai reply sent and persisted",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation.id,
                        "provider_event_id": event.provider_event_id,
                        "outbound_provider_message_id": outbound_message_provider_id,
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
    ) -> str:
        system_prompt = self._default_system_prompt
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is not None:
            system_prompt = agent_profile.system_prompt

        tool_definitions = self._build_tool_definitions()
        function_call_results: list[llm_dto.FunctionCallResultDTO] = []
        for _ in range(self._max_function_call_iterations):
            llm_input = llm_dto.GenerateReplyInputDTO(
                system_prompt=system_prompt,
                messages=llm_messages,
                tools=tool_definitions,
                function_call_results=function_call_results,
            )
            llm_reply = self._llm_provider.generate_reply(llm_input)
            if llm_reply.function_calls:
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
                continue

            if llm_reply.content.strip():
                return llm_reply.content
            break

        raise service_exceptions.ExternalProviderError("llm returned empty content")

    def _execute_function_call(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        try:
            if function_call.name == "request_schedule_approval":
                if self._scheduling_service is None:
                    return {"error": "scheduling service is not configured"}
                request_input_dto = scheduling_dto.RequestScheduleApprovalInputDTO.model_validate(
                    function_call.args
                )
                request = self._scheduling_service.request_schedule_approval(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    whatsapp_user_id=whatsapp_user_id,
                    input_dto=request_input_dto,
                )
                return {
                    "request_id": request.request_id,
                    "status": request.status,
                    "round_number": request.round_number,
                }

            if function_call.name == "confirm_selected_slot_and_create_event":
                if self._scheduling_service is None:
                    return {"error": "scheduling service is not configured"}
                confirm_input_dto = scheduling_dto.ConfirmSelectedSlotInputDTO.model_validate(
                    function_call.args
                )
                return self._confirm_selected_slot_with_retry(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    confirm_input_dto=confirm_input_dto,
                )

            if function_call.name == "handoff_to_human":
                if self._scheduling_service is None:
                    return {"error": "scheduling service is not configured"}
                handoff_input_dto = scheduling_dto.HandoffToHumanInputDTO.model_validate(
                    function_call.args
                )
                handoff_result = self._scheduling_service.handoff_to_human(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    input_dto=handoff_input_dto,
                )
                return {
                    "status": handoff_result["status"],
                    "control_mode": handoff_result["control_mode"],
                }

            return {"error": f"unknown function: {function_call.name}"}
        except pydantic.ValidationError as error:
            return {"error": str(error)}
        except service_exceptions.ServiceError as error:
            return {"error": str(error)}

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

    def _build_tool_definitions(self) -> list[llm_dto.FunctionDeclarationDTO]:
        return [
            llm_dto.FunctionDeclarationDTO(
                name="request_schedule_approval",
                description=(
                    "Crea o reintenta una solicitud de agendamiento para que el profesional revise preferencias del paciente."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "request_kind": {"type": "string", "enum": ["INITIAL", "RETRY"]},
                        "patient_preference_note": {"type": "string"},
                        "hard_constraints": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "rejection_summary": {"type": ["string", "null"]},
                    },
                    "required": ["request_kind", "patient_preference_note", "hard_constraints"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="confirm_selected_slot_and_create_event",
                description=(
                    "Confirma un horario elegido por el paciente y crea el evento en Google Calendar."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                        "slot_id": {"type": "string"},
                    },
                    "required": ["request_id", "slot_id"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="handoff_to_human",
                description=(
                    "Pasa la conversacion a modo humano cuando el paciente solicita un tema no relacionado o requiere atencion manual."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "summary_for_professional": {"type": "string"},
                    },
                    "required": ["reason", "summary_for_professional"],
                    "additionalProperties": False,
                },
            ),
        ]

    def _mark_event_processed(self, tenant_id: str, provider_event_id: str) -> None:
        processed_event = processed_webhook_event_entity.ProcessedWebhookEvent(
            provider_event_id=provider_event_id,
            tenant_id=tenant_id,
            processed_at=self._clock.now(),
        )
        self._processed_webhook_event_repository.save(processed_event)
