"""Slot-proposal sub-domain for scheduling.

What lives here:
  - submit_consultation_reason_for_review_impl: creates/updates the
    SchedulingRequest after the patient provides their reason, validates
    state, resolves location from agent profile.
  - resolve_consultation_review_impl: professional approves or rejects the
    consultation; transitions request to CONSULTATION_REJECTED or
    AWAITING_CONSULTATION_DETAILS.
  - cancel_active_request_impl: cancels any open (non-booked) request for a
    conversation.
  - escalate_patient_slot_rejection_impl: patient rejects all proposed slots
    and the request is sent back to AWAITING_CONSULTATION_REVIEW.
  - select_slot_for_confirmation_impl: patient picks one proposed slot;
    transitions to AWAITING_PAYMENT_CONFIRMATION (BEFORE_SESSION), or keeps
    AWAITING_PATIENT_CHOICE with selected_slot_id set (AFTER_SESSION or
    RESCHEDULE).

What does NOT live here:
  - Calendar event creation (booking.py).
  - Payment approval (payment_approval.py).
  - Conversation archiving or session closing (booking.py / transitions.py).
"""

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling.helpers as scheduling_helpers
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


# ---------------------------------------------------------------------------
# Location resolver (needs agent profile repo)
# ---------------------------------------------------------------------------


def resolve_location(
    appointment_modality: str,
    patient_location: str | None,
    fallback_patient_location: str | None,
    tenant_id: str | None,
    agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort | None,
) -> str:
    """Return the appointment location string for the given modality.

    For PRESENCIAL reads main_city from AgentProfile; falls back to the
    generic label "Presencial".  For virtual modalities returns the
    patient-provided location, raising when none is available.
    """
    if appointment_modality == "PRESENCIAL":
        if tenant_id is not None and agent_profile_repository is not None:
            profile = agent_profile_repository.get_by_tenant_id(tenant_id)
            if profile is not None and profile.identity is not None and profile.identity.main_city:
                return profile.identity.main_city
        return "Presencial"

    normalized_location = scheduling_helpers.normalize_patient_text(patient_location)
    if normalized_location is None:
        normalized_location = scheduling_helpers.normalize_patient_text(fallback_patient_location)
    if normalized_location is None:
        raise service_exceptions.InvalidStateError(
            "missing required patient data: patient_location; ask only for the patient's location now"
        )
    return normalized_location


# ---------------------------------------------------------------------------
# Resolve-request helper (needs scheduling repo for explicit request_id lookup)
# ---------------------------------------------------------------------------


def resolve_request_for_consultation_submission(
    tenant_id: str,
    conversation_id: str,
    existing_requests: list[scheduling_request_entity.SchedulingRequest],
    request_id: str | None,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
) -> scheduling_request_entity.SchedulingRequest | None:
    """Resolve the SR to update for a consultation-reason submission.

    Returns None when no matching SR exists (caller will create a new one).
    Raises EntityNotFoundError / AuthorizationError for explicit request_id
    mismatches.
    """
    if request_id is not None:
        request = scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        return request

    return scheduling_helpers.find_latest_request_by_statuses(
        requests=existing_requests,
        statuses=(
            "AWAITING_CONSULTATION_DETAILS",
            "AWAITING_CONSULTATION_REVIEW",
        ),
    )


# ---------------------------------------------------------------------------
# get_payment_timing helper (needs agent profile repo)
# ---------------------------------------------------------------------------


def get_payment_timing(
    tenant_id: str,
    agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort | None,
) -> str:
    """Return the current payment_timing for the tenant.

    Falls back to "BEFORE_SESSION" when no agent profile repo is wired
    (e.g. unit tests that don't inject it) — preserves existing behavior.
    """
    if agent_profile_repository is None:
        return "BEFORE_SESSION"
    profile = agent_profile_repository.get_by_tenant_id(tenant_id)
    if profile is None:
        return "BEFORE_SESSION"
    return profile.payment_timing


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


def submit_consultation_reason_for_review_impl(
    tenant_id: str,
    conversation_id: str,
    whatsapp_user_id: str,
    input_dto: scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    id_generator: id_generator_port.IdGeneratorPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
    agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Create or update a SchedulingRequest with the patient's consultation reason."""
    conversation = conversation_repository.get_conversation_by_id(tenant_id, conversation_id)
    if conversation is None:
        raise service_exceptions.EntityNotFoundError("conversation not found")

    now_value = clock.now()
    existing_requests = scheduling_repository.list_requests_by_conversation(
        tenant_id,
        conversation_id,
    )
    request = resolve_request_for_consultation_submission(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        existing_requests=existing_requests,
        request_id=input_dto.request_id,
        scheduling_repository=scheduling_repository,
    )
    if request is None:
        active_scheduling_request = scheduling_helpers.find_latest_request_by_statuses(
            requests=existing_requests,
            statuses=("AWAITING_PATIENT_CHOICE",),
        )
        if active_scheduling_request is not None:
            raise service_exceptions.InvalidStateError(
                "schedule options are already available; ask the patient to choose one numbered slot"
            )
        request = scheduling_request_entity.SchedulingRequest(
            id=id_generator.new_id(),
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
    if request.status == "AWAITING_PATIENT_CHOICE":
        raise service_exceptions.InvalidStateError(
            "schedule options are already available; ask the patient to choose one numbered slot"
        )

    consultation_reason = scheduling_helpers.coalesce_patient_text(
        primary=input_dto.consultation_reason,
        fallback=request.consultation_reason,
    )
    if consultation_reason is None:
        raise service_exceptions.InvalidStateError(
            "missing required patient data: consultation_reason; ask only for the consultation reason now"
        )

    request.consultation_reason = consultation_reason
    if input_dto.appointment_modality is not None:
        request.appointment_modality = input_dto.appointment_modality
        request.patient_location = resolve_location(
            appointment_modality=input_dto.appointment_modality,
            patient_location=input_dto.patient_location,
            fallback_patient_location=request.patient_location,
            tenant_id=tenant_id,
            agent_profile_repository=agent_profile_repository,
        )
    request.professional_note = None
    request.rejection_summary = None
    request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
    scheduling_repository.save_request(request)
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
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
    return scheduling_helpers.to_summary_dto(request)


def resolve_consultation_review_impl(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    input_dto: scheduling_dto.ConsultationReviewDecisionDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Apply the professional's decision to an AWAITING_CONSULTATION_REVIEW request."""
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
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

    now_value = clock.now()
    professional_note = scheduling_helpers.normalize_patient_text(input_dto.professional_note)

    if input_dto.decision == "REQUEST_MORE_INFO":
        if professional_note is None:
            raise service_exceptions.InvalidStateError(
                "professional_note is required when requesting more information"
            )
        request.professional_note = professional_note
        request.set_status("AWAITING_CONSULTATION_DETAILS", now_value)
    else:
        request.professional_note = professional_note
        request.set_status("CONSULTATION_REJECTED", now_value)

    scheduling_repository.save_request(request)
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
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
    return scheduling_helpers.to_summary_dto(request)


def cancel_active_request_impl(
    tenant_id: str,
    conversation_id: str,
    input_dto: scheduling_dto.CancelActiveSchedulingRequestInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Cancel the current open (non-booked) scheduling request for a conversation."""
    conversation = conversation_repository.get_conversation_by_id(tenant_id, conversation_id)
    if conversation is None:
        raise service_exceptions.EntityNotFoundError("conversation not found")

    request_list = scheduling_repository.list_requests_by_conversation(
        tenant_id,
        conversation_id,
    )
    open_request = scheduling_helpers.find_latest_request_by_statuses(
        requests=request_list,
        statuses=(
            "AWAITING_CONSULTATION_REVIEW",
            "AWAITING_CONSULTATION_DETAILS",
            "AWAITING_PATIENT_CHOICE",
            "AWAITING_PAYMENT_CONFIRMATION",
        ),
    )
    if open_request is None:
        raise service_exceptions.EntityNotFoundError("no active scheduling request found")

    now_value = clock.now()
    open_request.set_status("CANCELLED", now_value)
    cancellation_reason = scheduling_helpers.normalize_patient_text(input_dto.reason)
    if cancellation_reason is not None:
        open_request.professional_note = cancellation_reason
    scheduling_repository.save_request(open_request)
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=open_request.status,
        )
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
    return scheduling_helpers.to_summary_dto(open_request)


def escalate_patient_slot_rejection_impl(
    tenant_id: str,
    request_id: str,
    patient_preference_note: str,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Escalate a patient's slot rejection back to professional review."""
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")
    if request.status != "AWAITING_PATIENT_CHOICE":
        raise service_exceptions.InvalidStateError(
            "scheduling request is not waiting for patient choice"
        )

    now_value = clock.now()
    normalized_note = scheduling_helpers.normalize_patient_text(patient_preference_note)
    request.patient_preference_note = normalized_note
    request.selected_slot_id = None
    request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
    scheduling_repository.save_request(request)
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            new_status=request.status,
        )

    logger.info(
        "scheduling.patient_slot_rejection_escalated",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.patient_slot_rejection_escalated",
                message="patient rejected proposed slots; escalated back for professional review",
                data={
                    "tenant_id": tenant_id,
                    "request_id": request.id,
                    "patient_preference_note": normalized_note,
                },
            )
        },
    )
    return scheduling_helpers.to_summary_dto(request)


def select_slot_for_confirmation_impl(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    slot_id: str,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
    agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort | None,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    """Mark the given slot as SELECTED.

    For BEFORE_SESSION payment timing and non-RESCHEDULE requests the request
    transitions to AWAITING_PAYMENT_CONFIRMATION.  For AFTER_SESSION timing or
    RESCHEDULE requests the request stays in AWAITING_PATIENT_CHOICE with
    selected_slot_id set (payment step is skipped).
    """
    request = scheduling_repository.get_request_by_id(tenant_id, request_id)
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

    selected_slot = scheduling_helpers.find_selectable_slot(request, slot_id)
    if selected_slot is None:
        raise service_exceptions.InvalidStateError("selected slot is not available")

    payment_timing = get_payment_timing(
        tenant_id=tenant_id,
        agent_profile_repository=agent_profile_repository,
    )
    now_value = clock.now()

    for slot in request.slots:
        if slot.id == selected_slot.id:
            slot.status = "SELECTED"
        elif slot.status == "SELECTED":
            slot.status = "PROPOSED"

    request.selected_slot_id = selected_slot.id

    if payment_timing == "AFTER_SESSION" or request.request_kind == "RESCHEDULE":
        # AFTER_SESSION: skip the payment step entirely. Keep the request
        # in AWAITING_PATIENT_CHOICE with selected_slot_id set so the
        # runtime resolver derives state=COLLECTING_CONFIRMATION_DATA.
        # RESCHEDULE: also skip payment — the appointment was already paid.
        request.updated_at = now_value
        scheduling_repository.save_request(request)
        logger.info(
            "scheduling.slot_selected_skip_payment",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.slot_selected_skip_payment",
                    message="slot selected; payment step skipped (AFTER_SESSION or RESCHEDULE)",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "slot_id": selected_slot.id,
                        "reason": "RESCHEDULE"
                        if request.request_kind == "RESCHEDULE"
                        else "AFTER_SESSION",
                    },
                )
            },
        )
        return scheduling_helpers.to_summary_dto(request)

    # BEFORE_SESSION: standard flow — await payment confirmation.
    request.set_status("AWAITING_PAYMENT_CONFIRMATION", now_value)
    scheduling_repository.save_request(request)
    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
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
    return scheduling_helpers.to_summary_dto(request)
