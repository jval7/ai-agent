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

    def submit_consultation_reason_for_review(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO,
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
        request = self._resolve_request_for_consultation_submission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            existing_requests=existing_requests,
            request_id=input_dto.request_id,
        )
        if request is None:
            active_scheduling_request = self._find_latest_request_by_statuses(
                requests=existing_requests,
                statuses=(
                    "COLLECTING_PREFERENCES",
                    "AWAITING_PROFESSIONAL_SLOTS",
                    "AWAITING_PATIENT_CHOICE",
                ),
            )
            if active_scheduling_request is not None:
                raise service_exceptions.InvalidStateError(
                    "consultation reason already approved; continue with scheduling preferences and call request_schedule_approval"
                )
            request = scheduling_request_entity.SchedulingRequest(
                id=self._id_generator.new_id(),
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                request_kind="INITIAL",
                status="AWAITING_CONSULTATION_REVIEW",
                round_number=len(existing_requests) + 1,
                patient_preference_note=None,
                rejection_summary=None,
                professional_note=None,
                slots=[],
                slot_options_map={},
                selected_slot_id=None,
                calendar_event_id=None,
                created_at=now_value,
                updated_at=now_value,
            )

        if request.status in ("BOOKED", "HUMAN_HANDOFF", "CONSULTATION_REJECTED", "CANCELLED"):
            raise service_exceptions.InvalidStateError(
                "cannot submit consultation reason for a closed scheduling request"
            )
        if request.status in ("COLLECTING_PREFERENCES", "AWAITING_PROFESSIONAL_SLOTS"):
            raise service_exceptions.InvalidStateError(
                "consultation reason already approved; continue with scheduling preferences and call request_schedule_approval"
            )
        if request.status == "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "schedule options are already available; ask the patient to choose one numbered slot"
            )

        consultation_reason = self._coalesce_patient_text(
            primary=input_dto.consultation_reason,
            fallback=request.consultation_reason,
        )
        if consultation_reason is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: consultation_reason; ask only for the consultation reason now"
            )

        request.consultation_reason = consultation_reason
        request.professional_note = None
        request.rejection_summary = None
        request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
        self._scheduling_repository.save_request(request)
        logger.info(
            "scheduling.consultation_review_requested",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.consultation_review_requested",
                    message="consultation reason submitted for professional review",
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

    def resolve_consultation_review(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        input_dto: scheduling_dto.ConsultationReviewDecisionDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_CONSULTATION_REVIEW":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for consultation review"
            )

        now_value = self._clock.now()
        professional_note = self._normalize_patient_text(input_dto.professional_note)

        if input_dto.decision == "APPROVE":
            request.set_status("COLLECTING_PREFERENCES", now_value)
            request.professional_note = professional_note
        elif input_dto.decision == "REQUEST_MORE_INFO":
            if professional_note is None:
                raise service_exceptions.InvalidStateError(
                    "professional_note is required when requesting more information"
                )
            request.professional_note = professional_note
            request.set_status("AWAITING_CONSULTATION_DETAILS", now_value)
        else:
            request.professional_note = professional_note
            request.set_status("CONSULTATION_REJECTED", now_value)

        self._scheduling_repository.save_request(request)
        logger.info(
            "scheduling.consultation_review_resolved",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.consultation_review_resolved",
                    message="consultation review resolved by professional",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "decision": input_dto.decision,
                        "status": request.status,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def request_schedule_approval(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.RequestScheduleApprovalInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        del whatsapp_user_id
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        request = self._resolve_target_request_for_schedule(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=input_dto.request_id,
        )

        if request.status == "AWAITING_PROFESSIONAL_SLOTS":
            logger.info(
                "scheduling.request_reused",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="scheduling.request_reused",
                        message="existing open scheduling request reused",
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
        if request.status == "AWAITING_PATIENT_CHOICE":
            now_value = self._clock.now()
            resolved_location = self._resolve_location(
                appointment_modality=input_dto.appointment_modality,
                patient_location=input_dto.patient_location,
                fallback_patient_location=request.patient_location,
            )
            request.appointment_modality = input_dto.appointment_modality
            request.patient_location = resolved_location
            request.patient_preference_note = input_dto.patient_preference_note
            request.rejection_summary = input_dto.rejection_summary
            request.professional_note = "patient requested different schedule options"
            request.slots = []
            request.slot_options_map = {}
            request.selected_slot_id = None
            request.set_status("AWAITING_PROFESSIONAL_SLOTS", now_value)
            self._scheduling_repository.save_request(request)
            logger.info(
                "scheduling.request_reopened_after_patient_rejection",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="scheduling.request_reopened_after_patient_rejection",
                        message="patient rejected offered slots and scheduling request was reopened",
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

        if request.status != "COLLECTING_PREFERENCES":
            raise service_exceptions.InvalidStateError(
                "consultation reason must be approved before requesting schedule approval"
            )

        now_value = self._clock.now()
        resolved_location = self._resolve_location(
            appointment_modality=input_dto.appointment_modality,
            patient_location=input_dto.patient_location,
            fallback_patient_location=request.patient_location,
        )

        request.appointment_modality = input_dto.appointment_modality
        request.patient_location = resolved_location
        request.patient_preference_note = input_dto.patient_preference_note
        request.rejection_summary = input_dto.rejection_summary
        request.professional_note = None
        request.set_status("AWAITING_PROFESSIONAL_SLOTS", now_value)
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

    def cancel_active_request(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.CancelActiveSchedulingRequestInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        open_request = self._find_latest_request_by_statuses(
            requests=request_list,
            statuses=(
                "AWAITING_CONSULTATION_REVIEW",
                "AWAITING_CONSULTATION_DETAILS",
                "COLLECTING_PREFERENCES",
                "AWAITING_PROFESSIONAL_SLOTS",
                "AWAITING_PATIENT_CHOICE",
            ),
        )
        if open_request is None:
            raise service_exceptions.EntityNotFoundError("no active scheduling request found")

        now_value = self._clock.now()
        open_request.set_status("CANCELLED", now_value)
        cancellation_reason = self._normalize_patient_text(input_dto.reason)
        if cancellation_reason is not None:
            open_request.professional_note = cancellation_reason
        self._scheduling_repository.save_request(open_request)
        logger.info(
            "scheduling.request_cancelled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.request_cancelled",
                    message="scheduling request cancelled by patient",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": open_request.id,
                    },
                )
            },
        )
        return self._to_summary_dto(open_request)

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

        selected_slot = self._find_selectable_slot(request, input_dto.slot_id)
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

    def select_slot_for_confirmation(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        slot_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
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

        selected_slot = self._find_selectable_slot(request, slot_id)
        if selected_slot is None:
            raise service_exceptions.InvalidStateError("selected slot is not available")

        now_value = self._clock.now()
        for slot in request.slots:
            if slot.id == selected_slot.id:
                slot.status = "SELECTED"
            elif slot.status == "SELECTED":
                slot.status = "PROPOSED"

        request.selected_slot_id = selected_slot.id
        request.updated_at = now_value
        self._scheduling_repository.save_request(request)
        logger.info(
            "scheduling.slot_selected",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.slot_selected",
                    message="patient slot selection persisted",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "slot_id": selected_slot.id,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

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
            if request.status in (
                "BOOKED",
                "HUMAN_HANDOFF",
                "CONSULTATION_REJECTED",
                "CANCELLED",
            ):
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

    def _resolve_request_for_consultation_submission(
        self,
        tenant_id: str,
        conversation_id: str,
        existing_requests: list[scheduling_request_entity.SchedulingRequest],
        request_id: str | None,
    ) -> scheduling_request_entity.SchedulingRequest | None:
        if request_id is not None:
            request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
            if request is None:
                raise service_exceptions.EntityNotFoundError("scheduling request not found")
            if request.conversation_id != conversation_id:
                raise service_exceptions.AuthorizationError(
                    "scheduling request does not belong to conversation"
                )
            return request

        return self._find_latest_request_by_statuses(
            requests=existing_requests,
            statuses=(
                "AWAITING_CONSULTATION_DETAILS",
                "AWAITING_CONSULTATION_REVIEW",
            ),
        )

    def _resolve_target_request_for_schedule(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str | None,
    ) -> scheduling_request_entity.SchedulingRequest:
        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )

        if request_id is not None:
            request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
            if request is None:
                raise service_exceptions.EntityNotFoundError("scheduling request not found")
            if request.conversation_id != conversation_id:
                raise service_exceptions.AuthorizationError(
                    "scheduling request does not belong to conversation"
                )
            return request

        request = self._find_latest_request_by_statuses(
            requests=request_list,
            statuses=(
                "COLLECTING_PREFERENCES",
                "AWAITING_PROFESSIONAL_SLOTS",
                "AWAITING_PATIENT_CHOICE",
            ),
        )
        if request is None:
            raise service_exceptions.InvalidStateError(
                "consultation reason must be approved before requesting schedule approval"
            )
        return request

    def _find_latest_request_by_statuses(
        self,
        requests: list[scheduling_request_entity.SchedulingRequest],
        statuses: tuple[str, ...],
    ) -> scheduling_request_entity.SchedulingRequest | None:
        filtered_requests: list[scheduling_request_entity.SchedulingRequest] = []
        for request in requests:
            if request.status in statuses:
                filtered_requests.append(request)

        if not filtered_requests:
            return None
        sorted_requests = sorted(filtered_requests, key=lambda item: item.updated_at, reverse=True)
        return sorted_requests[0]

    def _find_selectable_slot(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        slot_id: str,
    ) -> scheduling_slot_entity.SchedulingSlot | None:
        for slot in request.slots:
            if slot.id == slot_id and slot.status in ("PROPOSED", "SELECTED"):
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

        if request.selected_slot_id == selected_slot.id:
            request.selected_slot_id = None

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

    def _coalesce_patient_text(
        self,
        primary: str | None,
        fallback: str | None,
    ) -> str | None:
        normalized_primary = self._normalize_patient_text(primary)
        if normalized_primary is not None:
            return normalized_primary
        return self._normalize_patient_text(fallback)

    def _coalesce_patient_age(
        self,
        primary: int | str | None,
        fallback: int | None,
    ) -> int | None:
        normalized_primary = self._normalize_patient_age(primary)
        if normalized_primary is not None:
            return normalized_primary
        return fallback

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

    def _resolve_location(
        self,
        appointment_modality: str,
        patient_location: str | None,
        fallback_patient_location: str | None,
    ) -> str:
        if appointment_modality == "PRESENCIAL":
            return "Cali"

        normalized_location = self._normalize_patient_text(patient_location)
        if normalized_location is None:
            normalized_location = self._normalize_patient_text(fallback_patient_location)
        if normalized_location is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_location; ask only for the patient's location now"
            )
        return normalized_location

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
            patient_first_name=request.patient_first_name,
            patient_last_name=request.patient_last_name,
            patient_age=request.patient_age,
            consultation_reason=request.consultation_reason,
            consultation_details=request.consultation_details,
            appointment_modality=request.appointment_modality,
            patient_location=request.patient_location,
            slot_options_map=request.slot_options_map,
            selected_slot_id=request.selected_slot_id,
            calendar_event_id=request.calendar_event_id,
            created_at=request.created_at,
            updated_at=request.updated_at,
            slots=slots,
        )
