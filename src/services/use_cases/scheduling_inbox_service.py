import datetime

import src.domain.entities.message as message_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.scheduling_slot_formatter as scheduling_slot_formatter
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class SchedulingInboxService:
    def __init__(
        self,
        scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
        scheduling_service: scheduling_service.SchedulingService,
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        whatsapp_connection_repository: (
            whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort
        ),
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._scheduling_repository = scheduling_repository
        self._scheduling_service = scheduling_service
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._conversation_repository = conversation_repository
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._whatsapp_provider = whatsapp_provider
        self._id_generator = id_generator
        self._clock = clock

    def list_requests(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> scheduling_dto.SchedulingRequestListResponseDTO:
        return self._scheduling_service.list_requests_by_tenant(tenant_id, status)

    def submit_professional_slots(
        self,
        claims: auth_dto.TokenClaimsDTO,
        conversation_id: str,
        request_id: str,
        submit_dto: scheduling_dto.ProfessionalSubmitSlotsDTO,
    ) -> scheduling_dto.ProfessionalSubmitSlotsResponseDTO:
        self._ensure_owner(claims)

        request = self._scheduling_repository.get_request_by_id(claims.tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_PROFESSIONAL_SLOTS":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for professional slots"
            )

        valid_slots: list[scheduling_slot_entity.SchedulingSlot] = []
        for slot_input in submit_dto.slots:
            self._validate_slot_duration(slot_input.start_at, slot_input.end_at)
            has_conflict = self._google_calendar_onboarding_service.has_conflict(
                tenant_id=claims.tenant_id,
                start_at=slot_input.start_at,
                end_at=slot_input.end_at,
            )
            if has_conflict:
                continue
            valid_slots.append(
                scheduling_slot_entity.SchedulingSlot(
                    id=slot_input.slot_id,
                    start_at=slot_input.start_at,
                    end_at=slot_input.end_at,
                    timezone=slot_input.timezone,
                    status="PROPOSED",
                )
            )

        if not valid_slots:
            raise service_exceptions.InvalidStateError("all submitted slots are unavailable")

        ordered_slots = sorted(valid_slots, key=lambda item: item.start_at)
        slot_options_map: dict[str, str] = {}
        for index, slot in enumerate(ordered_slots, start=1):
            slot_options_map[str(index)] = slot.id

        now_value = self._clock.now()
        request.slots = ordered_slots
        request.slot_options_map = slot_options_map
        request.selected_slot_id = None
        request.professional_note = submit_dto.professional_note
        request.set_status("AWAITING_PATIENT_CHOICE", now_value)
        self._scheduling_repository.save_request(request)

        conversation = self._conversation_repository.get_conversation_by_id(
            claims.tenant_id,
            conversation_id,
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")
        connection = self._whatsapp_connection_repository.get_by_tenant_id(claims.tenant_id)
        if connection is None:
            raise service_exceptions.InvalidStateError("whatsapp connection not found")
        if connection.access_token is None or connection.phone_number_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")

        assistant_text = self._build_resume_message(
            slots=ordered_slots,
            slot_options_map=slot_options_map,
        )
        outbound_provider_message_id = self._whatsapp_provider.send_text_message(
            access_token=connection.access_token,
            phone_number_id=connection.phone_number_id,
            whatsapp_user_id=request.whatsapp_user_id,
            text=assistant_text,
        )
        outbound_message = message_entity.Message(
            id=self._id_generator.new_id(),
            conversation_id=conversation.id,
            tenant_id=claims.tenant_id,
            direction="OUTBOUND",
            role="assistant",
            content=assistant_text,
            provider_message_id=outbound_provider_message_id,
            created_at=self._clock.now(),
        )
        self._conversation_repository.save_message(outbound_message)
        conversation.append_message(
            outbound_message.id,
            outbound_message.content,
            outbound_message.created_at,
        )
        self._conversation_repository.save_conversation(conversation)
        logger.info(
            "scheduling.professional_slots_submitted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.professional_slots_submitted",
                    message="professional submitted slots and conversation resumed",
                    data={
                        "tenant_id": claims.tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "slot_count": len(valid_slots),
                    },
                )
            },
        )
        return scheduling_dto.ProfessionalSubmitSlotsResponseDTO(
            status="AWAITING_PATIENT_CHOICE",
            slot_batch_id=request.id,
            outbound_message_id=outbound_provider_message_id,
            assistant_text=assistant_text,
        )

    def _build_resume_message(
        self,
        slots: list[scheduling_slot_entity.SchedulingSlot],
        slot_options_map: dict[str, str],
    ) -> str:
        slot_by_id: dict[str, scheduling_slot_entity.SchedulingSlot] = {}
        for slot in slots:
            slot_by_id[slot.id] = slot

        lines = ["Tengo estos horarios disponibles:"]
        for option_number in sorted(slot_options_map.keys(), key=int):
            slot_id = slot_options_map[option_number]
            slot_candidate = slot_by_id.get(slot_id)
            if slot_candidate is None:
                continue
            lines.append(
                scheduling_slot_formatter.format_slot_option_line(
                    option_number=option_number,
                    start_at=slot_candidate.start_at,
                    timezone_name=slot_candidate.timezone,
                )
            )
        lines.append("Responde solo con el numero de la opcion que prefieres (por ejemplo: 2).")
        return "\n".join(lines)

    def _validate_slot_duration(
        self,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
    ) -> None:
        duration_seconds = (end_at - start_at).total_seconds()
        if duration_seconds != 3600:
            raise service_exceptions.InvalidStateError("slots must be exactly 60 minutes")

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")
