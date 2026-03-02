import datetime
import re
import time
import typing
import unicodedata
import zoneinfo

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
        self._llm_empty_content_retry_backoff_seconds = [0.5, 1.0]
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
                confirm_input_dto = self._resolve_confirm_selected_slot_input(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    tool_input_dto=confirm_tool_input_dto,
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
    ) -> scheduling_dto.ConfirmSelectedSlotInputDTO:
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

        return scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=target_request.request_id,
            slot_id=resolved_slot_id,
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

        latest_user_text = self._get_latest_user_message_text(tenant_id, conversation_id)
        if latest_user_text is None:
            raise service_exceptions.InvalidStateError(
                "slot selection is ambiguous; ask patient to choose one specific slot"
            )

        option_number = self._extract_option_number(
            latest_user_text=latest_user_text,
            max_option_number=len(ordered_proposed_slots),
        )
        if option_number is not None:
            return ordered_proposed_slots[option_number - 1].slot_id

        slot_id_by_datetime = self._resolve_slot_id_from_datetime_mention(
            ordered_proposed_slots=ordered_proposed_slots,
            latest_user_text=latest_user_text,
        )
        if slot_id_by_datetime is not None:
            return slot_id_by_datetime

        raise service_exceptions.InvalidStateError(
            "slot selection is ambiguous; ask patient to choose one specific slot"
        )

    def _list_ordered_proposed_slots(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> list[scheduling_dto.SchedulingSlotDTO]:
        proposed_slots: list[scheduling_dto.SchedulingSlotDTO] = []
        for slot in request.slots:
            if slot.status == "PROPOSED":
                proposed_slots.append(slot)
        return sorted(proposed_slots, key=lambda item: item.start_at)

    def _get_latest_user_message_text(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> str | None:
        messages = self._conversation_repository.list_messages(tenant_id, conversation_id)
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        return None

    def _extract_option_number(
        self,
        latest_user_text: str,
        max_option_number: int,
    ) -> int | None:
        normalized_text = self._normalize_text(latest_user_text)
        exact_match = re.fullmatch(r"\s*(\d{1,2})\s*", normalized_text)
        if exact_match is not None:
            value = int(exact_match.group(1))
            if 1 <= value <= max_option_number:
                return value

        labeled_match = re.search(
            r"\b(opcion|numero|nro|#)\s*(\d{1,2})\b",
            normalized_text,
        )
        if labeled_match is None:
            return None

        value = int(labeled_match.group(2))
        if 1 <= value <= max_option_number:
            return value
        return None

    def _resolve_slot_id_from_datetime_mention(
        self,
        ordered_proposed_slots: list[scheduling_dto.SchedulingSlotDTO],
        latest_user_text: str,
    ) -> str | None:
        normalized_text = self._normalize_text(latest_user_text)
        mentioned_date_parts = self._extract_mentioned_date_parts(normalized_text)
        mentioned_days = self._extract_mentioned_days(normalized_text)
        mentioned_time_parts = self._extract_mentioned_time_parts(normalized_text)

        if not mentioned_date_parts and not mentioned_days and not mentioned_time_parts:
            return None

        candidate_slot_ids: list[str] = []
        for slot in ordered_proposed_slots:
            slot_local_start = self._to_slot_local_datetime(slot)
            if mentioned_date_parts:
                date_candidate = (slot_local_start.day, slot_local_start.month)
                if date_candidate not in mentioned_date_parts:
                    continue
            elif mentioned_days:
                if slot_local_start.day not in mentioned_days:
                    continue
            if mentioned_time_parts and not self._slot_matches_any_time_mention(
                slot_local_start=slot_local_start,
                time_mentions=mentioned_time_parts,
            ):
                continue
            candidate_slot_ids.append(slot.slot_id)

        if len(candidate_slot_ids) == 1:
            return candidate_slot_ids[0]
        return None

    def _extract_mentioned_date_parts(
        self,
        normalized_text: str,
    ) -> set[tuple[int, int]]:
        month_by_name = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "setiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }
        date_parts: set[tuple[int, int]] = set()
        for match in re.finditer(r"\b(\d{1,2})\s+de\s+([a-z]+)\b", normalized_text):
            day = int(match.group(1))
            month_name = match.group(2)
            month = month_by_name.get(month_name)
            if month is None:
                continue
            if 1 <= day <= 31:
                date_parts.add((day, month))
        return date_parts

    def _extract_mentioned_days(
        self,
        normalized_text: str,
    ) -> set[int]:
        days: set[int] = set()
        for match in re.finditer(r"\bel\s+(\d{1,2})\b", normalized_text):
            day = int(match.group(1))
            if 1 <= day <= 31:
                days.add(day)
        return days

    def _extract_mentioned_time_parts(
        self,
        normalized_text: str,
    ) -> list[tuple[int, int, str | None]]:
        time_parts: list[tuple[int, int, str | None]] = []
        for match in re.finditer(
            r"(?:a\s+las|a\s+la|las)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            normalized_text,
        ):
            hour = int(match.group(1))
            minute = 0
            if match.group(2) is not None:
                minute = int(match.group(2))
            meridiem = match.group(3)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                time_parts.append((hour, minute, meridiem))
        return time_parts

    def _slot_matches_any_time_mention(
        self,
        slot_local_start: datetime.datetime,
        time_mentions: list[tuple[int, int, str | None]],
    ) -> bool:
        for hour, minute, meridiem in time_mentions:
            if self._slot_matches_time_mention(slot_local_start, hour, minute, meridiem):
                return True
        return False

    def _slot_matches_time_mention(
        self,
        slot_local_start: datetime.datetime,
        hour: int,
        minute: int,
        meridiem: str | None,
    ) -> bool:
        if slot_local_start.minute != minute:
            return False

        if meridiem is None:
            slot_hour_12 = slot_local_start.hour % 12
            if slot_hour_12 == 0:
                slot_hour_12 = 12
            return hour == slot_local_start.hour or hour == slot_hour_12

        normalized_hour = hour
        if meridiem == "am":
            if hour == 12:
                normalized_hour = 0
        else:
            if hour < 12:
                normalized_hour = hour + 12

        return slot_local_start.hour == normalized_hour

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

    def _normalize_text(self, value: str) -> str:
        lowered_value = value.lower()
        normalized_value = unicodedata.normalize("NFD", lowered_value)
        return "".join(
            character for character in normalized_value if unicodedata.category(character) != "Mn"
        )

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
                    "Si request_id o slot_id no se incluyen, el backend intentara resolverlos automaticamente cuando no haya ambiguedad."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                        "slot_id": {"type": "string"},
                    },
                    "required": [],
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
