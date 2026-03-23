import re
import typing
import unicodedata

import src.infra.logs as app_logs
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.llm_provider_port as llm_provider_port
import src.services.agentic.tool_handlers.base as tool_handler_base
import src.services.agentic.tool_handlers.registry as tool_handler_registry_mod
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.scheduling_slot_formatter as scheduling_slot_formatter
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)

NUMERIC_PATTERN = re.compile(r"^\d+$")


def find_single_active_request_waiting_patient_choice(
    scheduling_svc: scheduling_service.SchedulingService,
    tenant_id: str,
    conversation_id: str,
) -> scheduling_dto.SchedulingRequestSummaryDTO | None:
    request_list = scheduling_svc.list_requests_by_conversation(
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


def request_contains_proposed_slot(
    request: scheduling_dto.SchedulingRequestSummaryDTO,
    slot_id: str,
) -> bool:
    return any(
        slot.slot_id == slot_id and slot.status in ("PROPOSED", "SELECTED")
        for slot in request.slots
    )


def resolve_slot_id_from_option_number(
    request: scheduling_dto.SchedulingRequestSummaryDTO,
    latest_user_text: str,
) -> str | None:
    normalized_text = latest_user_text.strip()
    if not NUMERIC_PATTERN.fullmatch(normalized_text):
        return None
    option_number = str(int(normalized_text))
    selected_slot_id = request.slot_options_map.get(option_number)
    if selected_slot_id is None:
        return None
    if not request_contains_proposed_slot(request=request, slot_id=selected_slot_id):
        return None
    return selected_slot_id


def resolve_slot_id_from_natural_language(
    request: scheduling_dto.SchedulingRequestSummaryDTO,
    latest_user_text: str,
    llm_provider: llm_provider_port.LlmProviderPort,
) -> str | None:
    option_lines = build_available_option_lines(request)
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
        llm_reply = llm_provider.generate_reply(llm_input)
    except service_exceptions.ExternalProviderError:
        return None

    resolved_text = llm_reply.content.strip()
    if not NUMERIC_PATTERN.fullmatch(resolved_text):
        return None
    option_number = str(int(resolved_text))
    selected_slot_id = request.slot_options_map.get(option_number)
    if selected_slot_id is None:
        return None
    if not request_contains_proposed_slot(request=request, slot_id=selected_slot_id):
        return None
    return selected_slot_id


def build_available_option_lines(
    request: scheduling_dto.SchedulingRequestSummaryDTO,
) -> list[str]:
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
    return option_lines


def build_slot_selection_retry_message(
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


def build_payment_instructions_message(
    audience_type: typing.Literal["ADULTS", "CHILDREN"] | None,
) -> str:
    if audience_type == "CHILDREN":
        session_price = "*$150.000 COP* por sesión"
        packages = (
            "• Paquete 3 sesiones: $427.500 (5% off, c/u $142.500)\n"
            "• Paquete 4 sesiones: $552.000 (8% off, c/u $138.000)"
        )
    else:
        session_price = "*$130.000 COP* por sesión"
        packages = (
            "• Paquete 3 sesiones: $370.500 (5% off, c/u $123.500)\n"
            "• Paquete 4 sesiones: $478.400 (8% off, c/u $119.600)"
        )
    return (
        f"¡Listo! El valor de la sesión es {session_price}\n\n"
        f"Si quieres aprovechar un paquete con descuento:\n"
        f"{packages}\n\n"
        "Para  continuar con el proceso de agendamiento de tu cita, realiza el pago por transferencia:\n"
        "• Nequi: 318 732 6409\n"
        "• A nombre de: Alejandra Escobar\n\n"
        "Cuando tengas el comprobante, me lo puedes enviar por aquí, por favor"
    )


HANDOFF_ACK_MESSAGE = "Claro, te comunico con una persona de nuestro equipo."
CANCEL_ACK_MESSAGE = (
    "Listo, cancelé este proceso. Si quieres retomarlo más adelante, te ayudo por aquí."
)
SLOT_REJECTION_ACK_MESSAGE = (
    "Entendido, voy a consultar otros horarios disponibles. Te aviso apenas tenga nuevas opciones."
)


def find_latest_assistant_message(
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    tenant_id: str,
    conversation_id: str,
) -> str | None:
    history_messages = conversation_repository.list_messages(
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


def is_explicit_override_intent(
    llm_provider: llm_provider_port.LlmProviderPort,
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
        llm_reply = llm_provider.generate_reply(llm_input)
    except service_exceptions.ExternalProviderError:
        return False

    normalized_reply = (
        unicodedata.normalize("NFKD", llm_reply.content).encode("ascii", "ignore").decode("ascii")
    )
    normalized_reply = normalized_reply.strip().upper()
    if not normalized_reply:
        return False
    first_token = normalized_reply.split()[0]
    return first_token in ("YES", "SI")


def should_execute_explicit_override_function(
    llm_provider: llm_provider_port.LlmProviderPort,
    function_name: str,
    latest_user_text: str,
    latest_assistant_text: str | None,
) -> bool:
    if function_name == "handoff_to_human":
        return is_explicit_override_intent(
            llm_provider=llm_provider,
            latest_user_text=latest_user_text,
            latest_assistant_text=latest_assistant_text,
            target_intent="HUMAN",
        )
    if function_name == "cancel_active_scheduling_request":
        return is_explicit_override_intent(
            llm_provider=llm_provider,
            latest_user_text=latest_user_text,
            latest_assistant_text=latest_assistant_text,
            target_intent="CANCEL",
        )
    return True


def execute_override_function_calls(
    function_calls: list[llm_dto.FunctionCallDTO],
    llm_provider: llm_provider_port.LlmProviderPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    tool_handler_registry: tool_handler_registry_mod.ToolHandlerRegistry,
    context: tool_handler_base.ToolExecutionContext,
    latest_user_text: str,
    log_event_prefix: str,
) -> str | None:
    latest_assistant_text = find_latest_assistant_message(
        conversation_repository=conversation_repository,
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
    )
    for function_call in function_calls:
        if not should_execute_explicit_override_function(
            llm_provider=llm_provider,
            function_name=function_call.name,
            latest_user_text=latest_user_text,
            latest_assistant_text=latest_assistant_text,
        ):
            logger.info(
                f"webhook.{log_event_prefix}_ignored_non_explicit",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name=f"webhook.{log_event_prefix}_ignored_non_explicit",
                        message=f"ignored {log_event_prefix} function because user intent was not explicit",
                        data={
                            "tenant_id": context.tenant_id,
                            "conversation_id": context.conversation_id,
                            "function_name": function_call.name,
                        },
                    )
                },
            )
            continue
        function_response_payload = tool_handler_registry.execute(context, function_call)
        if function_call.name == "handoff_to_human":
            if function_response_payload.get("status") == "HUMAN_HANDOFF":
                return HANDOFF_ACK_MESSAGE
            return None
        if function_call.name == "cancel_active_scheduling_request":
            if function_response_payload.get("status") == "CANCELLED":
                return CANCEL_ACK_MESSAGE
            return None
        if function_call.name == "close_session":
            return None
    return None
