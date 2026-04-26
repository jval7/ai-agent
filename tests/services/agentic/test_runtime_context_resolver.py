import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as inmemory_task_scheduler_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.services.agentic.runtime_context_resolver as runtime_context_resolver_mod
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_resolver_with_scheduling() -> tuple[
    runtime_context_resolver_mod.RuntimeContextResolver,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    scheduling_service.SchedulingService,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_repo = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    calendar_repo.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=NOW,
            connected_at=NOW,
        )
    )
    id_gen = fake_adapters.SequenceIdGenerator(["id-1", "id-2", "id-3"])
    clock = fake_adapters.FixedClock(NOW)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_svc = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_repo,
        google_calendar_provider=google_provider,
        id_generator=id_gen,
        clock=clock,
    )
    task_sched = inmemory_task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
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
    scheduling_svc = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
        google_calendar_onboarding_service=google_svc,
        id_generator=id_gen,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
    )
    resolver = runtime_context_resolver_mod.RuntimeContextResolver(
        scheduling_svc=scheduling_svc,
        conversation_repository=conversation_repo,
    )
    return resolver, scheduling_repo, conversation_repo, scheduling_svc


def test_resolve_returns_no_active_request_when_no_scheduling_service() -> None:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    resolver = runtime_context_resolver_mod.RuntimeContextResolver(
        scheduling_svc=None,
        conversation_repository=conversation_repo,
    )

    result = resolver.resolve("tenant-1", "conversation-1", None)

    assert result.state == "NO_ACTIVE_REQUEST"
    assert "handoff_to_human" in result.enabled_tool_names


def test_resolve_returns_awaiting_consultation_details_state() -> None:
    resolver, scheduling_repo, conversation_repo, _ = _build_resolver_with_scheduling()
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
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_DETAILS",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note="Aprobado",
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    result = resolver.resolve("tenant-1", "conv-1", None)

    assert result.state == "AWAITING_CONSULTATION_DETAILS"
    assert result.request_id == "req-1"
    assert result.professional_note == "Aprobado"
    assert "submit_consultation_reason_for_review" in result.enabled_tool_names


def test_resolve_returns_collecting_confirmation_data_when_slot_selected() -> None:
    resolver, scheduling_repo, conversation_repo, _ = _build_resolver_with_scheduling()
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
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            appointment_modality="PRESENCIAL",
            slots=[],
            slot_options_map={},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    result = resolver.resolve("tenant-1", "conv-1", None)

    assert result.state == "COLLECTING_CONFIRMATION_DATA"
    assert result.selected_slot_id == "slot-1"
    assert "confirm_selected_slot_and_create_event" in result.enabled_tool_names
    assert len(result.missing_confirmation_fields) > 0


def test_resolve_returns_post_booking_followup_for_booked_not_archived() -> None:
    resolver, scheduling_repo, conversation_repo, _ = _build_resolver_with_scheduling()
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
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
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
            calendar_event_id="cal-evt-1",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    result = resolver.resolve("tenant-1", "conv-1", None)

    assert result.state == "POST_BOOKING_FOLLOWUP"
    assert result.request_id == "req-1"
    assert "close_session" in result.enabled_tool_names


def test_resolve_returns_no_active_request_for_booked_already_archived() -> None:
    resolver, scheduling_repo, conversation_repo, _ = _build_resolver_with_scheduling()
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
            subsessions=[
                conversation_entity.ConversationSubsession(
                    scheduling_request_id="req-1",
                    calendar_event_id="cal-evt-1",
                    messages=[],
                    archived_at=NOW,
                    archived_reason="APPOINTMENT_BOOKED",
                )
            ],
        )
    )
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
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
            calendar_event_id="cal-evt-1",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    result = resolver.resolve("tenant-1", "conv-1", None)

    assert result.state == "NO_ACTIVE_REQUEST"


def test_compute_missing_confirmation_fields_does_not_require_phone_with_whatsapp_id() -> None:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    resolver = runtime_context_resolver_mod.RuntimeContextResolver(
        scheduling_svc=None,
        conversation_repository=conversation_repo,
    )
    request = scheduling_dto.SchedulingRequestSummaryDTO(
        request_id="req-1",
        conversation_id="conversation-1",
        whatsapp_user_id="573127457050",
        request_kind="INITIAL",
        status="AWAITING_PATIENT_CHOICE",
        round_number=1,
        patient_preference_note="despues de las 4 pm",
        rejection_summary=None,
        professional_note=None,
        patient_first_name="Jhon",
        patient_last_name="Valderrama",
        patient_age=33,
        consultation_reason="ansiedad",
        consultation_details=None,
        appointment_modality="VIRTUAL",
        patient_location="Cali",
        slot_options_map={"1": "slot-1"},
        selected_slot_id="slot-1",
        calendar_event_id=None,
        payment_amount_cop=None,
        payment_method=None,
        payment_status="PENDING",
        payment_updated_at=None,
        created_at=NOW,
        updated_at=NOW,
        slots=[],
    )

    missing_fields = resolver._compute_missing_confirmation_fields(
        request=request,
        known_patient=None,
    )

    assert "patient_email" in missing_fields
    assert "patient_phone" not in missing_fields


def test_compute_missing_fields_returns_empty_when_known_patient() -> None:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    resolver = runtime_context_resolver_mod.RuntimeContextResolver(
        scheduling_svc=None,
        conversation_repository=conversation_repo,
    )
    request = scheduling_dto.SchedulingRequestSummaryDTO(
        request_id="req-1",
        conversation_id="conversation-1",
        whatsapp_user_id="573127457050",
        request_kind="INITIAL",
        status="AWAITING_PATIENT_CHOICE",
        round_number=1,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        patient_first_name=None,
        patient_last_name=None,
        patient_age=None,
        consultation_reason=None,
        consultation_details=None,
        appointment_modality=None,
        patient_location=None,
        slot_options_map={},
        selected_slot_id=None,
        calendar_event_id=None,
        payment_amount_cop=None,
        payment_method=None,
        payment_status="PENDING",
        payment_updated_at=None,
        created_at=NOW,
        updated_at=NOW,
        slots=[],
    )
    known_patient = patient_entity.Patient(
        tenant_id="tenant-1",
        whatsapp_user_id="573127457050",
        first_name="Jhon",
        last_name="Valderrama",
        email="jhon@example.com",
        age=33,
        location="Cali",
        phone="573127457050",
        created_at=NOW,
    )

    missing_fields = resolver._compute_missing_confirmation_fields(
        request=request,
        known_patient=known_patient,
    )

    assert missing_fields == []


def test_resolve_post_booking_followup_includes_appointment_modality_and_location() -> None:
    resolver, scheduling_repo, conversation_repo, _ = _build_resolver_with_scheduling()
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
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-modal-1",
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
            selected_slot_id="slot-1",
            calendar_event_id="cal-evt-1",
            appointment_modality="PRESENCIAL",
            patient_location="Cali",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    result = resolver.resolve("tenant-1", "conv-1", None)

    assert result.state == "POST_BOOKING_FOLLOWUP"
    assert result.appointment_modality == "PRESENCIAL"
    assert result.patient_location == "Cali"
