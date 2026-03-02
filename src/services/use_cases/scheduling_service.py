import datetime

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service

logger = app_logs.get_logger(__name__)


class SchedulingService:
    def __init__(
        self,
        scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._scheduling_repository = scheduling_repository
        self._conversation_repository = conversation_repository
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._id_generator = id_generator
        self._clock = clock

    def list_requests_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> scheduling_dto.SchedulingRequestListResponseDTO:
        requests = self._scheduling_repository.list_requests_by_tenant(tenant_id, status)
        sorted_requests = sorted(requests, key=lambda item: item.updated_at, reverse=True)
        items = [self._to_summary_dto(item) for item in sorted_requests]
        return scheduling_dto.SchedulingRequestListResponseDTO(items=items)

    def list_requests_by_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestListResponseDTO:
        requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id, conversation_id
        )
        sorted_requests = sorted(requests, key=lambda item: item.updated_at, reverse=True)
        items = [self._to_summary_dto(item) for item in sorted_requests]
        return scheduling_dto.SchedulingRequestListResponseDTO(items=items)

    def request_schedule_approval(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.RequestScheduleApprovalInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        now_value = self._clock.now()
        existing_requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        round_number = len(existing_requests) + 1
        request = scheduling_request_entity.SchedulingRequest(
            id=self._id_generator.new_id(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            whatsapp_user_id=whatsapp_user_id,
            request_kind=input_dto.request_kind,
            status="AWAITING_PROFESSIONAL_SLOTS",
            round_number=round_number,
            patient_preference_note=input_dto.patient_preference_note,
            rejection_summary=input_dto.rejection_summary,
            professional_note=None,
            slots=[],
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
        self._scheduling_repository.save_request(request)
        logger.info(
            "scheduling.request_created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.request_created",
                    message="scheduling request created",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "status": request.status,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def confirm_selected_slot_and_create_event(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO,
    ) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, input_dto.request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for patient choice"
            )

        selected_slot = self._find_available_slot(request, input_dto.slot_id)
        if selected_slot is None:
            raise service_exceptions.InvalidStateError("selected slot is not available")

        has_conflict = self._google_calendar_onboarding_service.has_conflict(
            tenant_id=tenant_id,
            start_at=selected_slot.start_at,
            end_at=selected_slot.end_at,
        )
        now_value = self._clock.now()
        if has_conflict:
            return self._mark_selected_slot_conflict(request, selected_slot, now_value)

        try:
            normalized_summary = input_dto.event_summary.strip()
            if not normalized_summary:
                raise service_exceptions.InvalidStateError("event summary cannot be empty")
            event = self._google_calendar_onboarding_service.create_event(
                tenant_id=tenant_id,
                start_at=selected_slot.start_at,
                end_at=selected_slot.end_at,
                summary=normalized_summary,
            )
        except service_exceptions.ExternalProviderError as error:
            if self._is_google_conflict_error(str(error)):
                return self._mark_selected_slot_conflict(request, selected_slot, now_value)
            raise
        for slot in request.slots:
            if slot.id == selected_slot.id:
                slot.status = "BOOKED"
            elif slot.status == "PROPOSED":
                slot.status = "REJECTED"

        request.selected_slot_id = selected_slot.id
        request.calendar_event_id = event.event_id
        request.set_status("BOOKED", now_value)
        self._scheduling_repository.save_request(request)
        return scheduling_dto.ConfirmSelectedSlotResponseDTO(
            status="BOOKED",
            request_id=request.id,
            selected_slot_id=selected_slot.id,
            calendar_event_id=event.event_id,
            remaining_slot_ids=[],
        )

    def handoff_to_human(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.HandoffToHumanInputDTO,
    ) -> dict[str, str]:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        now_value = self._clock.now()
        conversation.set_control_mode("HUMAN", now_value)
        self._conversation_repository.save_conversation(conversation)

        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        for request in request_list:
            if request.status in ("BOOKED", "HUMAN_HANDOFF"):
                continue
            request.set_status("HUMAN_HANDOFF", now_value)
            request.professional_note = input_dto.summary_for_professional
            self._scheduling_repository.save_request(request)

        logger.info(
            "scheduling.handoff_to_human",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.handoff_to_human",
                    message="conversation switched to human due scheduling handoff",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "reason": input_dto.reason,
                    },
                )
            },
        )
        return {
            "status": "HUMAN_HANDOFF",
            "control_mode": "HUMAN",
        }

    def _find_available_slot(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        slot_id: str,
    ) -> scheduling_slot_entity.SchedulingSlot | None:
        for slot in request.slots:
            if slot.id == slot_id and slot.status == "PROPOSED":
                return slot
        return None

    def _list_remaining_slot_ids(
        self,
        request: scheduling_request_entity.SchedulingRequest,
    ) -> list[str]:
        remaining_slot_ids: list[str] = []
        for slot in request.slots:
            if slot.status == "PROPOSED":
                remaining_slot_ids.append(slot.id)
        return remaining_slot_ids

    def _mark_selected_slot_conflict(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        selected_slot: scheduling_slot_entity.SchedulingSlot,
        now_value: datetime.datetime,
    ) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
        for slot in request.slots:
            if slot.id == selected_slot.id:
                slot.status = "UNAVAILABLE"
                break

        remaining_slot_ids = self._list_remaining_slot_ids(request)
        if remaining_slot_ids:
            request.set_status("AWAITING_PATIENT_CHOICE", now_value)
        else:
            request.set_status("AWAITING_PROFESSIONAL_SLOTS", now_value)
        self._scheduling_repository.save_request(request)
        return scheduling_dto.ConfirmSelectedSlotResponseDTO(
            status="SLOT_CONFLICT",
            request_id=request.id,
            selected_slot_id=None,
            calendar_event_id=None,
            remaining_slot_ids=remaining_slot_ids,
        )

    def _is_google_conflict_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "status=409" in normalized_message or "conflict" in normalized_message

    def _to_summary_dto(
        self,
        request: scheduling_request_entity.SchedulingRequest,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        slots = []
        for slot in request.slots:
            slots.append(
                scheduling_dto.SchedulingSlotDTO(
                    slot_id=slot.id,
                    start_at=slot.start_at,
                    end_at=slot.end_at,
                    timezone=slot.timezone,
                    status=slot.status,
                )
            )

        return scheduling_dto.SchedulingRequestSummaryDTO(
            request_id=request.id,
            conversation_id=request.conversation_id,
            whatsapp_user_id=request.whatsapp_user_id,
            request_kind=request.request_kind,
            status=request.status,
            round_number=request.round_number,
            patient_preference_note=request.patient_preference_note,
            rejection_summary=request.rejection_summary,
            professional_note=request.professional_note,
            selected_slot_id=request.selected_slot_id,
            calendar_event_id=request.calendar_event_id,
            created_at=request.created_at,
            updated_at=request.updated_at,
            slots=slots,
        )
