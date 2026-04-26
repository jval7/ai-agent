import datetime
import typing

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.services.agentic.tool_handlers.base as tool_handler_base
import src.services.agentic.tool_handlers.confirm_attendance_received_handler as confirm_attendance_received_handler
import src.services.dto.llm_dto as llm_dto
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters


def _build_handler() -> tuple[
    confirm_attendance_received_handler.ConfirmAttendanceReceivedHandler,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repo = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["id-1"])
    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()

    calendar_connection_repo.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="access-1",
            refresh_token="refresh-1",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            connected_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )

    google_svc = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repo,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
    )
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="Eres un asistente.",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo,
    )
    svc = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
        google_calendar_onboarding_service=google_svc,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
    )
    handler = confirm_attendance_received_handler.ConfirmAttendanceReceivedHandler(
        scheduling_svc=svc,
    )
    return handler, scheduling_repo


def _seed_attendance_request(
    scheduling_repo: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    status: typing.Literal[
        "AWAITING_CONSULTATION_REVIEW",
        "AWAITING_CONSULTATION_DETAILS",
        "AWAITING_PATIENT_CHOICE",
        "AWAITING_PAYMENT_CONFIRMATION",
        "AWAITING_ATTENDANCE_CONFIRMATION",
        "CONSULTATION_REJECTED",
        "CANCELLED",
        "BOOKED",
        "SESSION_CLOSED",
        "HUMAN_HANDOFF",
    ] = "AWAITING_ATTENDANCE_CONFIRMATION",
) -> str:
    request = scheduling_request_entity.SchedulingRequest(
        id="attend-req-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="RETRY",
        status=status,
        round_number=2,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        slots=[],
        slot_options_map={},
        selected_slot_id=None,
        calendar_event_id=None,
        source_appointment_id="original-req-1",
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    scheduling_repo.save_request(request)
    return request.id


def _make_context() -> tool_handler_base.ToolExecutionContext:
    return tool_handler_base.ToolExecutionContext(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
    )


def _make_function_call() -> llm_dto.FunctionCallDTO:
    return llm_dto.FunctionCallDTO(name="confirm_attendance_received", args={}, call_id=None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_handler_closes_session_when_attendance_request_exists() -> None:
    handler, scheduling_repo = _build_handler()
    request_id = _seed_attendance_request(scheduling_repo)

    result = handler.execute(_make_context(), _make_function_call())

    assert result["status"] == "SESSION_CLOSED"
    assert result["action"] == "closed"

    closed = scheduling_repo.get_request_by_id("tenant-1", request_id)
    assert closed is not None
    assert closed.status == "SESSION_CLOSED"


def test_handler_returns_skipped_when_no_attendance_request() -> None:
    """If there is no AWAITING_ATTENDANCE_CONFIRMATION request, handler returns skipped."""
    handler, scheduling_repo = _build_handler()
    # Seed a request in a different status.
    _seed_attendance_request(scheduling_repo, status="BOOKED")

    result = handler.execute(_make_context(), _make_function_call())

    assert result["status"] == "skipped"
    # The BOOKED request must not have been touched.
    unchanged = scheduling_repo.get_request_by_id("tenant-1", "attend-req-1")
    assert unchanged is not None
    assert unchanged.status == "BOOKED"
