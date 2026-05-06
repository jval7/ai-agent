import datetime

import pytest

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
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.services.agentic.tool_handlers.base as tool_handler_base
import src.services.agentic.tool_handlers.submit_reschedule_for_review_handler as submit_reschedule_for_review_handler
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_handler() -> tuple[
    submit_reschedule_for_review_handler.SubmitRescheduleForReviewHandler,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_repo = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(NOW)
    id_generator = fake_adapters.SequenceIdGenerator(["new-reschedule-req-1"])
    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()

    calendar_repo.save(
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
            updated_at=NOW,
            connected_at=NOW,
        )
    )
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=NOW,
            updated_at=NOW,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )

    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="Eres un asistente.",
            updated_at=NOW,
        )
    )
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo,
    )
    google_svc = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_repo,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
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
    handler = submit_reschedule_for_review_handler.SubmitRescheduleForReviewHandler(
        scheduling_svc=svc,
    )
    return handler, scheduling_repo


def _seed_booked_request(
    scheduling_repo: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
) -> None:
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="original-req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="BOOKED",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            consultation_reason="Ansiedad",
            appointment_modality="PRESENCIAL",
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-booked",
                    start_at=datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 3, 1, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="BOOKED",
                )
            ],
            slot_options_map={},
            selected_slot_id="slot-booked",
            calendar_event_id="cal-event-1",
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _make_context() -> tool_handler_base.ToolExecutionContext:
    return tool_handler_base.ToolExecutionContext(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
    )


def test_handler_creates_reschedule_sr_and_returns_request_id() -> None:
    handler, scheduling_repo = _build_handler()
    _seed_booked_request(scheduling_repo)

    function_call = llm_dto.FunctionCallDTO(
        name="submit_reschedule_for_review",
        args={"original_request_id": "original-req-1", "reason": "Cambio de agenda"},
        call_id=None,
    )
    result = handler.execute(_make_context(), function_call)

    assert result["request_id"] == "new-reschedule-req-1"
    assert result["status"] == "AWAITING_CONSULTATION_REVIEW"

    child = scheduling_repo.get_request_by_id("tenant-1", "new-reschedule-req-1")
    assert child is not None
    assert child.request_kind == "RESCHEDULE"
    assert child.source_appointment_id == "original-req-1"


def test_handler_returns_error_for_non_booked_request() -> None:
    handler, scheduling_repo = _build_handler()
    # Seed a non-BOOKED request
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="original-req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    function_call = llm_dto.FunctionCallDTO(
        name="submit_reschedule_for_review",
        args={"original_request_id": "original-req-1"},
        call_id=None,
    )
    with pytest.raises(service_exceptions.InvalidStateError):
        handler.execute(_make_context(), function_call)
