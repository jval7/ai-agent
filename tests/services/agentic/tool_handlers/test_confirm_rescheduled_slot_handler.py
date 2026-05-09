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
import src.services.agentic.tool_handlers.confirm_rescheduled_slot_handler as confirm_rescheduled_slot_handler
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
NEW_START = datetime.datetime(2026, 5, 1, 15, 0, tzinfo=datetime.UTC)
NEW_END = datetime.datetime(2026, 5, 1, 16, 0, tzinfo=datetime.UTC)


def _build_handler() -> tuple[
    confirm_rescheduled_slot_handler.ConfirmRescheduledSlotHandler,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_repo = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(NOW)
    id_generator = fake_adapters.SequenceIdGenerator(["unused-id-1"])
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
    handler = confirm_rescheduled_slot_handler.ConfirmRescheduledSlotHandler(
        scheduling_svc=svc,
    )
    return handler, scheduling_repo, provider


def _seed_booked_and_reschedule_requests(
    scheduling_repo: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
) -> None:
    """Seed a BOOKED original SR and a RESCHEDULE SR with a selected slot."""
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
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="reschedule-req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="RESCHEDULE",
            status="AWAITING_PATIENT_CHOICE",
            round_number=2,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            consultation_reason="Ansiedad",
            appointment_modality="PRESENCIAL",
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="new-slot-1",
                    start_at=NEW_START,
                    end_at=NEW_END,
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "new-slot-1"},
            selected_slot_id="new-slot-1",
            calendar_event_id=None,
            source_appointment_id="original-req-1",
            source_appointment_kind="SCHEDULING_REQUEST",
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


def test_handler_moves_calendar_event_and_promotes_child_to_booked() -> None:
    handler, scheduling_repo, provider = _build_handler()
    _seed_booked_and_reschedule_requests(scheduling_repo)

    function_call = llm_dto.FunctionCallDTO(
        name="confirm_rescheduled_slot",
        args={"request_id": "reschedule-req-1"},
        call_id=None,
    )
    result = handler.execute(_make_context(), function_call)

    # The RESCHEDULE child now owns the appointment so the conversation lands
    # in POST_BOOKING_FOLLOWUP.
    assert result["request_id"] == "reschedule-req-1"
    assert result["status"] == "BOOKED"

    # Calendar must have been updated.
    assert len(provider.updated_events) == 1
    assert provider.updated_events[0].start_at == NEW_START

    # RESCHEDULE child becomes BOOKED with the calendar event ownership.
    reschedule = scheduling_repo.get_request_by_id("tenant-1", "reschedule-req-1")
    assert reschedule is not None
    assert reschedule.status == "BOOKED"
    assert reschedule.calendar_event_id is not None

    # Original SR is closed and detached from the calendar event so the
    # agenda renders only one appointment.
    original = scheduling_repo.get_request_by_id("tenant-1", "original-req-1")
    assert original is not None
    assert original.status == "SESSION_CLOSED"
    assert original.calendar_event_id is None


def test_handler_returns_error_when_no_slot_selected() -> None:
    handler, scheduling_repo, _provider = _build_handler()
    # Seed original BOOKED request
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
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id="cal-event-1",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    # Seed RESCHEDULE SR with no selected slot
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="reschedule-req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="RESCHEDULE",
            status="AWAITING_PATIENT_CHOICE",
            round_number=2,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,  # no slot selected
            calendar_event_id=None,
            source_appointment_id="original-req-1",
            source_appointment_kind="SCHEDULING_REQUEST",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    function_call = llm_dto.FunctionCallDTO(
        name="confirm_rescheduled_slot",
        args={"request_id": "reschedule-req-1"},
        call_id=None,
    )
    with pytest.raises(service_exceptions.InvalidStateError):
        handler.execute(_make_context(), function_call)
