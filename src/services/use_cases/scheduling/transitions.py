"""Scheduling session-lifecycle transitions sub-domain.

What lives here:
  - handoff_to_human_impl: switches the conversation to HUMAN mode and saves a
    summary note on open scheduling requests.
  - close_session_impl: archives the subsession (booking or manual close),
    transitions all active requests to SESSION_CLOSED, syncs tags.
  - close_attendance_confirmation: finds an AWAITING_ATTENDANCE_CONFIRMATION
    request and closes it immediately (no Cloud Task delay).
  - auto_close_booked_request: triggered by a Cloud Task; archives and closes a
    BOOKED or AWAITING_ATTENDANCE_CONFIRMATION request.

What does NOT live here:
  - The _run_transition_with_graph wrapper — that stays in SchedulingService
    (the facade) because it owns the AgentWorkflowPort dependency.
  - Slot-level state changes (slot_proposals.py, booking.py).
  - Payment approval (payment_approval.py).
"""

import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling.booking as scheduling_booking
import src.services.use_cases.scheduling.helpers as scheduling_helpers
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


def handoff_to_human_impl(
    tenant_id: str,
    conversation_id: str,
    input_dto: scheduling_dto.HandoffToHumanInputDTO,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> dict[str, str]:
    conversation = conversation_repository.get_conversation_by_id(tenant_id, conversation_id)
    if conversation is None:
        raise service_exceptions.EntityNotFoundError("conversation not found")

    now_value = clock.now()
    conversation.set_control_mode("HUMAN", now_value)
    conversation_repository.save_conversation(conversation)

    request_list = scheduling_repository.list_requests_by_conversation(
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
        request.professional_note = input_dto.summary_for_professional
        scheduling_repository.save_request(request)

    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="HUMAN_HANDOFF",
        )

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


def close_session_impl(
    tenant_id: str,
    conversation_id: str,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> dict[str, str]:
    request_list = scheduling_repository.list_requests_by_conversation(
        tenant_id,
        conversation_id,
    )
    terminal_statuses = {
        "SESSION_CLOSED",
        "CANCELLED",
        "CONSULTATION_REJECTED",
        "HUMAN_HANDOFF",
    }
    booked_request = None
    active_requests = []
    for request in request_list:
        if request.status in terminal_statuses:
            continue
        active_requests.append(request)
        if request.status == "BOOKED":
            booked_request = request

    now_value = clock.now()

    if booked_request is not None:
        scheduling_booking.archive_conversation_subsession_after_booking(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            scheduling_request_id=booked_request.id,
            calendar_event_id=booked_request.calendar_event_id or "",
            now_value=now_value,
            conversation_repository=conversation_repository,
        )
    else:
        scheduling_booking.archive_conversation_subsession_manual_close(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            now_value=now_value,
            conversation_repository=conversation_repository,
        )

    for request in active_requests:
        request.set_status("SESSION_CLOSED", now_value)
        scheduling_repository.save_request(request)

    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="SESSION_CLOSED",
        )

    logger.info(
        "scheduling.session_closed",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.session_closed",
                message="conversation session closed and archived",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "closed_request_ids": [request.id for request in active_requests],
                },
            )
        },
    )
    return {
        "status": "SESSION_CLOSED",
    }


def close_attendance_confirmation(
    tenant_id: str,
    conversation_id: str,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> dict[str, str]:
    """Close the session immediately when the patient confirms attendance.

    Finds the active AWAITING_ATTENDANCE_CONFIRMATION request for the
    conversation, archives the subsession via manual-close, and transitions
    the request to SESSION_CLOSED.  Returns a no-op result if no such
    request exists (idempotent).
    """
    request_list = scheduling_repository.list_requests_by_conversation(
        tenant_id,
        conversation_id,
    )
    attendance_request = scheduling_helpers.find_latest_request_by_statuses(
        requests=request_list,
        statuses=("AWAITING_ATTENDANCE_CONFIRMATION",),
    )
    if attendance_request is None:
        logger.info(
            "scheduling.close_attendance_skipped",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
            },
        )
        return {"status": "skipped", "action": "no_active_attendance_request"}

    now_value = clock.now()
    scheduling_booking.archive_conversation_subsession_manual_close(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        now_value=now_value,
        conversation_repository=conversation_repository,
    )
    attendance_request.set_status("SESSION_CLOSED", now_value)
    scheduling_repository.save_request(attendance_request)

    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="SESSION_CLOSED",
        )

    logger.info(
        "scheduling.attendance_confirmed_session_closed",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.attendance_confirmed_session_closed",
                message="patient confirmed attendance; session closed immediately",
                data={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "request_id": attendance_request.id,
                },
            )
        },
    )
    return {"status": "SESSION_CLOSED", "action": "closed"}


def auto_close_booked_request(
    tenant_id: str,
    scheduling_request_id: str,
    scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
    conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    clock: clock_port.ClockPort,
    tag_service: tag_service_module.TagService | None,
) -> dict[str, str]:
    request = scheduling_repository.get_request_by_id(tenant_id, scheduling_request_id)
    if request is None:
        raise service_exceptions.EntityNotFoundError("scheduling request not found")

    if request.status not in ("BOOKED", "AWAITING_ATTENDANCE_CONFIRMATION"):
        logger.info(
            "scheduling.auto_close_skipped",
            extra={
                "request_id": scheduling_request_id,
                "current_status": request.status,
            },
        )
        return {"status": request.status, "action": "skipped"}

    now_value = clock.now()
    if request.status == "BOOKED":
        scheduling_booking.archive_conversation_subsession_after_booking(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            scheduling_request_id=request.id,
            calendar_event_id=request.calendar_event_id or "",
            now_value=now_value,
            conversation_repository=conversation_repository,
        )
    else:
        # AWAITING_ATTENDANCE_CONFIRMATION: reminder-reply request with no calendar event.
        scheduling_booking.archive_conversation_subsession_manual_close(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            now_value=now_value,
            conversation_repository=conversation_repository,
        )

    request.set_status("SESSION_CLOSED", now_value)
    scheduling_repository.save_request(request)

    if tag_service is not None:
        tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            new_status=request.status,
        )

    logger.info(
        "scheduling.auto_close_completed",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="scheduling.auto_close_completed",
                message="session auto-closed after timeout",
                data={
                    "tenant_id": tenant_id,
                    "request_id": scheduling_request_id,
                },
            )
        },
    )
    return {"status": "SESSION_CLOSED", "action": "closed"}
