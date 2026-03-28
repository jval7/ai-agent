import src.infra.logs as app_logs
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

logger = app_logs.get_logger(__name__)


class WaitingPatientChoiceGuard(base.ConversationGuard):
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
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
        active_request = guard_helpers.find_single_active_request_waiting_patient_choice(
            scheduling_svc=self._scheduling_service,
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
        )
        if active_request is None:
            return None
        if active_request.selected_slot_id is not None:
            return None

        normalized_text = context.latest_user_text.strip()
        if guard_helpers.NUMERIC_PATTERN.fullmatch(normalized_text):
            return None

        natural_language_slot_id = guard_helpers.resolve_slot_id_from_natural_language(
            request=active_request,
            latest_user_text=context.latest_user_text,
            llm_provider=self._llm_provider,
        )
        if natural_language_slot_id is not None:
            try:
                self._scheduling_service.select_slot_for_confirmation(
                    tenant_id=context.tenant_id,
                    conversation_id=context.conversation_id,
                    request_id=active_request.request_id,
                    slot_id=natural_language_slot_id,
                )
            except service_exceptions.ServiceError:
                return guard_helpers.build_slot_selection_retry_message(active_request)
            return None

        function_calls = self._resolve_override_function_calls(
            latest_user_text=context.latest_user_text,
            active_request=active_request,
        )
        tool_context = tool_handler_base.ToolExecutionContext(
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            whatsapp_user_id=context.whatsapp_user_id,
        )
        override_result = guard_helpers.execute_override_function_calls(
            function_calls=function_calls,
            llm_provider=self._llm_provider,
            conversation_repository=self._conversation_repository,
            tool_handler_registry=self._tool_handler_registry,
            context=tool_context,
            latest_user_text=context.latest_user_text,
            log_event_prefix="patient_choice_override",
        )
        if override_result is not None:
            return override_result

        patient_preference = self._detect_slot_rejection_preference(
            latest_user_text=context.latest_user_text,
            active_request=active_request,
        )
        if patient_preference is not None:
            return self._escalate_slot_rejection(
                tenant_id=context.tenant_id,
                active_request=active_request,
                patient_preference=patient_preference,
            )

        return None

    def _resolve_override_function_calls(
        self,
        latest_user_text: str,
        active_request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> list[llm_dto.FunctionCallDTO]:
        modality = active_request.appointment_modality
        if modality is None:
            modality = "PRESENCIAL"
        current_preference = active_request.patient_preference_note
        if current_preference is None:
            current_preference = ""
        location_value = active_request.patient_location
        if location_value is None:
            location_value = ""

        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=(
                "Estado interno: el paciente esta en AWAITING_PATIENT_CHOICE. "
                "Los horarios ya fueron propuestos y normalmente debe responder con numero. "
                "Decide si corresponde llamar una funcion: "
                "1) handoff_to_human si pide explicitamente humano, "
                "2) cancel_active_scheduling_request si pide cancelar. "
                "Si no aplica ninguna, no llames funciones."
            ),
            messages=[
                llm_dto.ChatMessageDTO(
                    role="user",
                    content=(
                        f"request_id_activo: {active_request.request_id}\n"
                        f"modalidad_actual: {modality}\n"
                        f"ubicacion_actual: {location_value}\n"
                        f"preferencia_actual: {current_preference}\n"
                        f"mensaje_paciente: {latest_user_text}\n"
                        "Si el paciente rechaza los horarios, NO llames ninguna funcion; "
                        "el profesional propondra nuevos horarios desde el panel."
                    ),
                )
            ],
            tools=self._tool_definition_registry.build_tool_definitions(
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

    def _detect_slot_rejection_preference(
        self,
        latest_user_text: str,
        active_request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str | None:
        option_lines = guard_helpers.build_available_option_lines(active_request)
        if not option_lines:
            return None

        options_block = "\n".join(option_lines)
        llm_input = llm_dto.GenerateReplyInputDTO(
            system_prompt=(
                "Eres un asistente que analiza si el paciente esta rechazando los horarios propuestos "
                "o expresando restricciones/preferencias de disponibilidad en vez de elegir una opcion concreta.\n"
                "Responde con un resumen breve de la preferencia del paciente en estos casos:\n"
                "- El paciente indica que ninguno de los horarios le sirve.\n"
                "- El paciente dice que no puede en esos dias/horas y sugiere otros.\n"
                "- El paciente expresa restricciones de disponibilidad o preferencias generales de dias/horas "
                "(por ejemplo: 'no puedo los martes', 'prefiero lunes o jueves', 'en la manana me queda dificil') "
                "SIN seleccionar una opcion especifica, incluso si los dias preferidos coinciden parcialmente "
                "con los horarios propuestos. Lo importante es que NO esta eligiendo un horario concreto "
                "de la lista, sino comunicando su disponibilidad general.\n"
                "Ejemplos de respuesta: 'Prefiere miercoles en la tarde', 'No puede martes, prefiere lunes o jueves', "
                "'Prefiere horarios en la manana'.\n"
                "Responde NINGUNA unicamente si el paciente esta intentando elegir uno de los horarios "
                "propuestos (por numero o descripcion), o si esta haciendo una pregunta que no tiene que ver "
                "con preferencias de horario."
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
        return guard_helpers.SLOT_REJECTION_ACK_MESSAGE
