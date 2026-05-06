import typing

import src.domain.entities.patient as patient_entity
import src.ports.conversation_repository_port as conversation_repository_port
import src.services.agentic.state_models as agentic_state_models
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service

RuntimePromptContext = agentic_state_models.RuntimePromptContext


def enabled_tools_for_state(state: str) -> list[str]:
    """Returns the tool whitelist for a given runtime state.

    Module-level function so the prompt lab and other test harnesses can
    build the same tool set the runtime uses without instantiating the
    full RuntimeContextResolver.
    """
    if state == "NO_ACTIVE_REQUEST":
        return [
            "submit_consultation_reason_for_review",
            "submit_reschedule_for_review",
            "close_session",
            "handoff_to_human",
            "cancel_active_scheduling_request",
        ]
    if state == "AWAITING_CONSULTATION_DETAILS":
        return [
            "submit_consultation_reason_for_review",
            "handoff_to_human",
            "cancel_active_scheduling_request",
        ]
    if state == "AWAITING_PATIENT_CHOICE":
        return [
            "select_proposed_slot",
            "reject_proposed_slots",
            "handoff_to_human",
            "cancel_active_scheduling_request",
        ]
    if state == "AWAITING_PAYMENT_CONFIRMATION":
        return [
            "handoff_to_human",
            "cancel_active_scheduling_request",
        ]
    if state == "AWAITING_ATTENDANCE_CONFIRMATION":
        return [
            "confirm_attendance_received",
            "submit_reschedule_for_review",
            "handoff_to_human",
        ]
    if state == "COLLECTING_CONFIRMATION_DATA":
        return [
            "confirm_selected_slot_and_create_event",
            "confirm_rescheduled_slot",
            "handoff_to_human",
            "cancel_active_scheduling_request",
        ]
    if state == "POST_BOOKING_FOLLOWUP":
        return [
            "close_session",
            "handoff_to_human",
        ]
    return ["handoff_to_human", "cancel_active_scheduling_request"]


class RuntimeContextResolver:
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService | None,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    ) -> None:
        self._scheduling_svc = scheduling_svc
        self._conversation_repository = conversation_repository

    def resolve(
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
            # No SR open in this conversation. Look for a previously BOOKED or
            # already SESSION_CLOSED appointment in the same conversation so the
            # bot can offer the reschedule flow when the patient comes back to
            # ask for a change. Returns None when there is no prior appointment
            # (e.g. brand-new conversations).
            last_booked_request_id = self._find_last_booked_request_id(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            )
            return RuntimePromptContext(
                state="NO_ACTIVE_REQUEST",
                last_booked_request_id=last_booked_request_id,
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
                    request_kind=self._to_request_kind(latest_open_request.request_kind),
                    appointment_modality=latest_open_request.appointment_modality,
                    patient_location=latest_open_request.patient_location,
                    patient_preference_note=latest_open_request.patient_preference_note,
                    enabled_tool_names=self._enabled_tools_for_state("AWAITING_PATIENT_CHOICE"),
                )

            selected_slot = self._find_slot(
                request=latest_open_request,
                slot_id=latest_open_request.selected_slot_id,
            )
            return RuntimePromptContext(
                state="COLLECTING_CONFIRMATION_DATA",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                request_kind=self._to_request_kind(latest_open_request.request_kind),
                appointment_modality=latest_open_request.appointment_modality,
                patient_location=latest_open_request.patient_location,
                patient_preference_note=latest_open_request.patient_preference_note,
                selected_slot_id=latest_open_request.selected_slot_id,
                appointment_start_at=selected_slot.start_at if selected_slot else None,
                appointment_end_at=selected_slot.end_at if selected_slot else None,
                patient_first_name=latest_open_request.patient_first_name,
                missing_confirmation_fields=self._compute_missing_confirmation_fields(
                    request=latest_open_request,
                    known_patient=known_patient,
                ),
                enabled_tool_names=self._enabled_tools_for_state("COLLECTING_CONFIRMATION_DATA"),
            )
        if request_status == "AWAITING_PAYMENT_CONFIRMATION":
            selected_slot = self._find_slot(
                request=latest_open_request,
                slot_id=latest_open_request.selected_slot_id,
            )
            return RuntimePromptContext(
                state="AWAITING_PAYMENT_CONFIRMATION",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                appointment_modality=latest_open_request.appointment_modality,
                selected_slot_id=latest_open_request.selected_slot_id,
                appointment_start_at=selected_slot.start_at if selected_slot else None,
                appointment_end_at=selected_slot.end_at if selected_slot else None,
                patient_first_name=latest_open_request.patient_first_name,
                enabled_tool_names=self._enabled_tools_for_state("AWAITING_PAYMENT_CONFIRMATION"),
            )
        if request_status == "AWAITING_ATTENDANCE_CONFIRMATION":
            selected_slot = self._find_slot(
                request=latest_open_request,
                slot_id=latest_open_request.selected_slot_id,
            )
            return RuntimePromptContext(
                state="AWAITING_ATTENDANCE_CONFIRMATION",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                request_kind=self._to_request_kind(latest_open_request.request_kind),
                appointment_modality=latest_open_request.appointment_modality,
                appointment_start_at=selected_slot.start_at if selected_slot else None,
                appointment_end_at=selected_slot.end_at if selected_slot else None,
                patient_first_name=latest_open_request.patient_first_name,
                enabled_tool_names=self._enabled_tools_for_state(
                    "AWAITING_ATTENDANCE_CONFIRMATION"
                ),
            )
        if request_status == "AWAITING_CONSULTATION_REVIEW":
            return RuntimePromptContext(
                state="AWAITING_CONSULTATION_REVIEW",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                professional_note=latest_open_request.professional_note,
                enabled_tool_names=self._enabled_tools_for_state("AWAITING_CONSULTATION_REVIEW"),
            )
        if request_status == "BOOKED":
            if self._is_session_already_archived(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                scheduling_request_id=latest_open_request.request_id,
            ):
                return RuntimePromptContext(
                    state="NO_ACTIVE_REQUEST",
                    enabled_tool_names=self._enabled_tools_for_state("NO_ACTIVE_REQUEST"),
                )
            selected_slot = self._find_slot(
                request=latest_open_request,
                slot_id=latest_open_request.selected_slot_id,
            )
            return RuntimePromptContext(
                state="POST_BOOKING_FOLLOWUP",
                request_id=latest_open_request.request_id,
                request_status=request_status,
                request_kind=self._to_request_kind(latest_open_request.request_kind),
                appointment_modality=latest_open_request.appointment_modality,
                patient_location=latest_open_request.patient_location,
                selected_slot_id=latest_open_request.selected_slot_id,
                appointment_start_at=selected_slot.start_at if selected_slot else None,
                appointment_end_at=selected_slot.end_at if selected_slot else None,
                patient_first_name=latest_open_request.patient_first_name,
                enabled_tool_names=self._enabled_tools_for_state("POST_BOOKING_FOLLOWUP"),
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
        if self._scheduling_svc is None:
            return None

        request_list = self._scheduling_svc.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        for request in request_list.items:
            if request.status in (
                "AWAITING_CONSULTATION_DETAILS",
                "AWAITING_CONSULTATION_REVIEW",
                "AWAITING_PATIENT_CHOICE",
                "AWAITING_PAYMENT_CONFIRMATION",
                "AWAITING_ATTENDANCE_CONFIRMATION",
                "BOOKED",
            ):
                return request
        return None

    def _find_last_booked_request_id(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> str | None:
        """Returns the request_id of the most recent BOOKED or SESSION_CLOSED
        scheduling request in this conversation, or None if there is no prior
        appointment.

        Used in NO_ACTIVE_REQUEST to surface a previously booked appointment so
        the bot can offer the reschedule flow when the patient comes back.
        Initial-flow requests in non-terminal states are returned by
        _find_latest_open_scheduling_request and handled separately.
        """
        if self._scheduling_svc is None:
            return None

        request_list = self._scheduling_svc.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        # Items are returned newest-first; pick the first BOOKED, fall back to
        # SESSION_CLOSED so the bot can still anchor a reschedule on a closed
        # successful flow.
        latest_session_closed: str | None = None
        for request in request_list.items:
            if request.status == "BOOKED":
                return request.request_id
            if request.status == "SESSION_CLOSED" and latest_session_closed is None:
                latest_session_closed = request.request_id
        return latest_session_closed

    def _find_slot(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        slot_id: str | None,
    ) -> scheduling_dto.SchedulingSlotDTO | None:
        if slot_id is None:
            return None
        for slot in request.slots:
            if slot.slot_id == slot_id:
                return slot
        return None

    def _is_session_already_archived(
        self,
        tenant_id: str,
        conversation_id: str,
        scheduling_request_id: str,
    ) -> bool:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id,
            conversation_id,
        )
        if conversation is None:
            return False
        for subsession in conversation.subsessions:
            if subsession.scheduling_request_id == scheduling_request_id:
                return True
        return False

    def _enabled_tools_for_state(self, state: str) -> list[str]:
        return enabled_tools_for_state(state)

    def _to_request_kind(
        self, kind: str
    ) -> "typing.Literal['INITIAL', 'RETRY', 'RESCHEDULE'] | None":
        if kind in ("INITIAL", "RETRY", "RESCHEDULE"):
            return kind  # type: ignore[return-value]
        return None

    def _compute_missing_confirmation_fields(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        known_patient: patient_entity.Patient | None,
    ) -> list[str]:
        if known_patient is not None:
            return []

        missing_fields: list[str] = []

        first = (request.patient_first_name or "").strip() or None
        last = (request.patient_last_name or "").strip() or None
        if first is None and last is None:
            missing_fields.append("patient_full_name")
        if request.patient_age is None:
            missing_fields.append("patient_age")
        if request.consultation_reason is None:
            missing_fields.append("consultation_reason")

        requires_location = request.appointment_modality == "VIRTUAL"
        if requires_location and request.patient_location is None:
            missing_fields.append("patient_location")

        missing_fields.append("patient_email")
        whatsapp_id_normalized = (request.whatsapp_user_id or "").strip() or None
        if whatsapp_id_normalized is None:
            missing_fields.append("patient_phone")
        return missing_fields
