import datetime
import json
import re
import time
import typing
import zoneinfo

import pydantic

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.processed_webhook_event as processed_webhook_event_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.blacklist_repository_port as blacklist_repository_port
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.llm_provider_port as llm_provider_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class ResolvedPatientProfile(pydantic.BaseModel):
    first_name: str
    last_name: str
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


class SlotSelectionResolution(pydantic.BaseModel):
    slot_id: str | None


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
        sleep_seconds: typing.Callable[[float], None] | None = None,
    ) -> None:
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._conversation_repository = conversation_repository
        self._patient_repository = patient_repository
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
        self._llm_empty_content_retry_backoff_seconds = [0.5, 1.0]
        self._professional_signature = "Psi. Alejandra Escobar"
        self._email_pattern = re.compile(
            r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
        )
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
        known_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id=tenant_id,
            whatsapp_user_id=event.whatsapp_user_id,
        )

        try:
            assistant_text = self._generate_reply_with_tools(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                whatsapp_user_id=event.whatsapp_user_id,
                llm_messages=llm_messages,
                known_patient=known_patient,
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
        known_patient: patient_entity.Patient | None,
    ) -> str:
        system_prompt = self._default_system_prompt
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is not None:
            system_prompt = agent_profile.system_prompt
        system_prompt = self._build_system_prompt_with_patient_context(
            base_system_prompt=system_prompt,
            known_patient=known_patient,
        )

        tool_definitions = self._build_tool_definitions()
        function_call_results: list[llm_dto.FunctionCallResultDTO] = []
        for _ in range(self._max_function_call_iterations):
            llm_input = llm_dto.GenerateReplyInputDTO(
                system_prompt=system_prompt,
                messages=llm_messages,
                tools=tool_definitions,
                function_call_results=function_call_results,
            )
            llm_reply = self._request_llm_reply_with_retry(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                llm_input=llm_input,
            )
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
            continue

        raise service_exceptions.ExternalProviderError("llm returned empty content")

    def _build_system_prompt_with_patient_context(
        self,
        base_system_prompt: str,
        known_patient: patient_entity.Patient | None,
    ) -> str:
        if known_patient is None:
            return base_system_prompt
        patient_context_lines = [
            "Known patient profile (reuse this context and avoid asking repeated data):",
            f"- patient_first_name: {known_patient.first_name}",
            f"- patient_last_name: {known_patient.last_name}",
            f"- patient_email: {known_patient.email}",
            f"- patient_age: {known_patient.age}",
            f"- consultation_reason: {known_patient.consultation_reason}",
            f"- patient_location: {known_patient.location}",
            f"- patient_phone: {known_patient.phone}",
            "If patient data is already known and still valid, do not ask for it again.",
        ]
        patient_context = "\n".join(patient_context_lines)
        return f"{base_system_prompt}\n\n{patient_context}"

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
        try:
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
                return confirm_result

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
            return {"error": str(error)}
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
            return {"error": str(error)}

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
            resolved_slot_id = self._resolve_slot_id_from_context(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request=target_request,
            )
        resolved_patient_profile, patient_exists = self._resolve_patient_profile_for_confirmation(
            tenant_id=tenant_id,
            whatsapp_user_id=target_request.whatsapp_user_id,
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

    def _resolve_slot_id_from_context(
        self,
        tenant_id: str,
        conversation_id: str,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str:
        ordered_proposed_slots = self._list_ordered_proposed_slots(request)
        if len(ordered_proposed_slots) == 1:
            first_slot = ordered_proposed_slots[0]
            return first_slot.slot_id

        recent_user_messages = self._list_recent_user_message_texts(tenant_id, conversation_id)
        if not recent_user_messages:
            raise service_exceptions.InvalidStateError(
                "slot selection is ambiguous; ask patient to choose one specific slot"
            )

        slot_id = self._resolve_slot_id_with_llm(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            ordered_proposed_slots=ordered_proposed_slots,
            recent_user_messages=recent_user_messages,
        )
        if slot_id is not None:
            return slot_id

        raise service_exceptions.InvalidStateError(
            "slot selection is ambiguous; ask patient to choose one specific slot"
        )

    def _resolve_slot_id_with_llm(
        self,
        tenant_id: str,
        conversation_id: str,
        ordered_proposed_slots: list[scheduling_dto.SchedulingSlotDTO],
        recent_user_messages: list[str],
    ) -> str | None:
        slot_lines: list[str] = []
        for index, slot in enumerate(ordered_proposed_slots, start=1):
            slot_local_start = self._to_slot_local_datetime(slot)
            slot_local_end = slot.end_at.astimezone(slot_local_start.tzinfo)
            slot_lines.append(
                f"- index: {index}; slot_id: {slot.slot_id}; "
                f"start_local: {slot_local_start.isoformat()}; "
                f"end_local: {slot_local_end.isoformat()}; "
                f"timezone: {slot.timezone}"
            )

        chronological_user_messages = list(reversed(recent_user_messages[:12]))
        user_message_lines: list[str] = []
        for index, message in enumerate(chronological_user_messages, start=1):
            user_message_lines.append(f"- user_{index}: {message}")

        resolver_user_prompt = (
            "Selecciona el slot_id que mejor corresponde a la eleccion del paciente.\n\n"
            "Slots disponibles:\n"
            f"{chr(10).join(slot_lines)}\n\n"
            "Mensajes recientes del paciente (orden cronologico):\n"
            f"{chr(10).join(user_message_lines)}\n\n"
            "Responde solo JSON valido con una de estas formas:\n"
            '{"slot_id":"<slot_id_valido>"}\n'
            '{"slot_id":null}'
        )
        resolver_system_prompt = (
            "Eres un resolvedor semantico de seleccion de horarios para agendamiento.\n"
            "El paciente puede escribir de cualquier forma, incluyendo lenguaje natural, "
            "numero, palabra, abreviaciones o referencias indirectas.\n"
            "Tu tarea es elegir un unico slot_id entre los slots disponibles.\n"
            "Si no hay evidencia suficiente o hay ambiguedad real, responde slot_id null.\n"
            "No inventes slots y no agregues texto fuera del JSON."
        )
        resolver_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=resolver_system_prompt,
            messages=[llm_dto.ChatMessageDTO(role="user", content=resolver_user_prompt)],
            tools=[],
            function_call_results=[],
        )
        resolver_reply = self._request_llm_reply_with_retry(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            llm_input=resolver_input,
        )
        if resolver_reply.function_calls:
            return None

        resolution = self._parse_slot_selection_resolution(resolver_reply.content)
        if resolution is None:
            return None
        if resolution.slot_id is None:
            return None

        for slot in ordered_proposed_slots:
            if slot.slot_id == resolution.slot_id:
                return resolution.slot_id
        return None

    def _parse_slot_selection_resolution(
        self,
        llm_content: str,
    ) -> SlotSelectionResolution | None:
        normalized_content = llm_content.strip()
        if normalized_content == "":
            return None
        try:
            parsed_payload = json.loads(normalized_content)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed_payload, dict):
            return None
        try:
            return SlotSelectionResolution.model_validate(parsed_payload)
        except pydantic.ValidationError:
            return None

    def _resolve_patient_profile_for_confirmation(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
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
                    first_name=existing_patient.first_name,
                    last_name=existing_patient.last_name,
                    email=existing_patient.email,
                    age=existing_patient.age,
                    consultation_reason=existing_patient.consultation_reason,
                    location=existing_patient.location,
                    phone=existing_patient.phone,
                ),
                True,
            )

        patient_first_name = self._normalize_patient_text(tool_input_dto.patient_first_name)
        if patient_first_name is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_first_name; ask only for the patient's first name now"
            )

        patient_last_name = self._normalize_patient_text(tool_input_dto.patient_last_name)
        if patient_last_name is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_last_name; ask only for the patient's last name now"
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

        patient_age = self._normalize_patient_age(tool_input_dto.patient_age)
        if patient_age is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_age; ask only for the patient's age now"
            )
        if patient_age < 1 or patient_age > 120:
            raise service_exceptions.InvalidStateError(
                "patient_age is invalid; ask only for age as a whole number between 1 and 120"
            )

        consultation_reason = self._normalize_patient_text(tool_input_dto.consultation_reason)
        if consultation_reason is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: consultation_reason; ask only for the consultation reason now"
            )

        patient_location = self._normalize_patient_text(tool_input_dto.patient_location)
        if patient_location is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_location; ask only for the patient's location now"
            )

        return (
            ResolvedPatientProfile(
                first_name=patient_first_name,
                last_name=patient_last_name,
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
        return (
            f"{resolved_patient_profile.first_name} {resolved_patient_profile.last_name}"
            f"/ {self._professional_signature}"
        )

    def _log_existing_patient_mismatch(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        existing_patient: patient_entity.Patient,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
    ) -> None:
        mismatched_fields: list[str] = []

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
            first_name=patient_profile.first_name,
            last_name=patient_profile.last_name,
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

    def _normalize_patient_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        return normalized_value

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

    def _list_ordered_proposed_slots(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> list[scheduling_dto.SchedulingSlotDTO]:
        proposed_slots: list[scheduling_dto.SchedulingSlotDTO] = []
        for slot in request.slots:
            if slot.status == "PROPOSED":
                proposed_slots.append(slot)
        return sorted(proposed_slots, key=lambda item: item.start_at)

    def _list_recent_user_message_texts(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> list[str]:
        messages = self._conversation_repository.list_messages(tenant_id, conversation_id)
        user_messages: list[str] = []
        for message in reversed(messages):
            if message.role == "user":
                user_messages.append(message.content)
        return user_messages

    def _to_slot_local_datetime(
        self,
        slot: scheduling_dto.SchedulingSlotDTO,
    ) -> datetime.datetime:
        timezone_name = slot.timezone.strip()
        if timezone_name == "":
            return slot.start_at
        try:
            slot_timezone = zoneinfo.ZoneInfo(timezone_name)
        except zoneinfo.ZoneInfoNotFoundError:
            return slot.start_at
        return slot.start_at.astimezone(slot_timezone)

    def _request_contains_proposed_slot(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        slot_id: str,
    ) -> bool:
        return any(slot.slot_id == slot_id and slot.status == "PROPOSED" for slot in request.slots)

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

    def _build_tool_definitions(self) -> list[llm_dto.FunctionDeclarationDTO]:
        return [
            llm_dto.FunctionDeclarationDTO(
                name="request_schedule_approval",
                description=(
                    "Crea o reintenta la busqueda de disponibilidad de agenda segun las preferencias del paciente."
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
                    "required": ["patient_preference_note"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="confirm_selected_slot_and_create_event",
                description=(
                    "Confirma un horario elegido por el paciente y crea el evento en Google Calendar. "
                    "Si el perfil del paciente ya existe en contexto, reutilizalo y no repitas preguntas innecesarias. "
                    "Si el perfil no existe, antes de llamar esta tool recolecta paso a paso y en mensajes separados: "
                    "patient_first_name, patient_last_name, patient_email, patient_phone, patient_age, consultation_reason y patient_location. "
                    "patient_phone puede tomarse del numero de WhatsApp si ya esta disponible. "
                    "No pidas todos los datos en un solo mensaje. "
                    "Si request_id o slot_id no se incluyen, el backend intentara resolverlos automaticamente cuando no haya ambiguedad."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                        "slot_id": {"type": "string"},
                        "patient_first_name": {"type": "string"},
                        "patient_last_name": {"type": "string"},
                        "patient_email": {"type": "string"},
                        "patient_phone": {"type": "string"},
                        "patient_age": {"type": ["integer", "string"]},
                        "consultation_reason": {"type": "string"},
                        "patient_location": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="handoff_to_human",
                description=(
                    "Pasa la conversacion a modo humano solo cuando el paciente solicita "
                    "explicitamente la intervencion de una persona humana."
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
