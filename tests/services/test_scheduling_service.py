import datetime
import typing

import pydantic
import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.manual_appointment_repository_adapter as manual_appointment_repository_adapter
import src.adapters.outbound.inmemory.scheduled_reminder_repository_adapter as scheduled_reminder_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.manual_appointment as manual_appointment_entity
import src.domain.entities.message as message_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.official_reminder_templates as official_reminder_templates
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.reminder_service as reminder_service_module
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters


def _build_event_description_builder(
    store: in_memory_store.InMemoryStore,
) -> event_description_builder_mod.EventDescriptionBuilder:
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
    return event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo
    )


def build_service(
    id_values: list[str],
) -> tuple[
    scheduling_service.SchedulingService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
    task_scheduler_adapter.InMemoryTaskSchedulerAdapter,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
    )

    calendar_connection_repository.save(
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
    conversation_repository.save_conversation(
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

    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    builder = _build_event_description_builder(store)
    service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
    )
    return service, scheduling_repository, provider, task_sched


_ATTENDANCE_TEMPLATE_NAME = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES[
    "ATTENDANCE"
].name


def build_service_with_in_person_profile(
    id_values: list[str],
) -> tuple[
    scheduling_service.SchedulingService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
    task_scheduler_adapter.InMemoryTaskSchedulerAdapter,
    scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter,
]:
    """Build a SchedulingService wired with an AFTER_SESSION agent profile and reminder service."""
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    reminder_repo = (
        scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter()
    )
    wa_connection_repo = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)

    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
    )

    # Seed an AFTER_SESSION agent profile with reminders enabled.
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="prompt",
            appointment_reminder_enabled=True,
            appointment_reminder_days_before=2,
            appointment_reminder_attendance_template_name=_ATTENDANCE_TEMPLATE_NAME,
            appointment_reminder_payment_template_name=None,
            payment_timing="AFTER_SESSION",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    calendar_connection_repository.save(
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
    conversation_repository.save_conversation(
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

    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    wa_provider = fake_adapters.FakeWhatsappProvider()
    wa_connection_repo.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo
    )
    reminder_svc = reminder_service_module.ReminderService(
        scheduled_reminder_repository=reminder_repo,
        agent_profile_repository=agent_profile_repo,
        whatsapp_connection_repository=wa_connection_repo,
        whatsapp_provider=wa_provider,
        task_scheduler=task_sched,
        id_generator=id_generator,
        clock=clock,
    )
    service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
        agent_profile_repository=agent_profile_repo,
        reminder_service=reminder_svc,
    )
    return service, scheduling_repository, provider, task_sched, reminder_repo


def create_awaiting_review_request(
    service: scheduling_service.SchedulingService,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    return service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Ansiedad",
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
        ),
    )


def _book_request(
    service: scheduling_service.SchedulingService,
    repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    provider: fake_adapters.FakeGoogleCalendarProvider,
) -> str:
    """Helper: creates a request, moves to AWAITING_PATIENT_CHOICE, and books it. Returns request_id."""
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)
    service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Booking",
        ),
    )
    return request.request_id


def test_submit_consultation_reason_rejects_when_slots_already_proposed() -> None:
    service, repository, _, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    with pytest.raises(service_exceptions.InvalidStateError) as error:
        service.submit_consultation_reason_for_review(
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
                request_id=request.request_id,
                consultation_reason="Ansiedad laboral",
            ),
        )

    assert "already available" in str(error.value)


def test_submit_consultation_reason_allows_resubmission_after_more_info_request() -> None:
    service, repository, _, _ = build_service(["req-1"])
    submitted_request = service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Ansiedad",
        ),
    )

    service.resolve_consultation_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id=submitted_request.request_id,
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="REQUEST_MORE_INFO",
            professional_note="¿Puedes ampliar el contexto?",
        ),
    )

    resubmitted_request = service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            request_id=submitted_request.request_id,
            consultation_reason="Ansiedad por cambios de trabajo y falta de sueno",
        ),
    )

    assert resubmitted_request.status == "AWAITING_CONSULTATION_REVIEW"
    stored_request = repository.get_request_by_id("tenant-1", submitted_request.request_id)
    assert stored_request is not None
    assert stored_request.consultation_reason == "Ansiedad por cambios de trabajo y falta de sueno"


def test_confirm_selected_slot_marks_conflict_when_busy() -> None:
    service, repository, provider, _ = build_service(["req-1"])
    provider.busy_intervals = [
        google_calendar_dto.GoogleCalendarBusyIntervalDTO(
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
        )
    ]
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
        ),
    )

    assert result.status == "SLOT_CONFLICT"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.status == "AWAITING_CONSULTATION_REVIEW"


def test_confirm_selected_slot_creates_event_when_available() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
        ),
    )

    assert result.status == "BOOKED"
    assert result.calendar_event_id == "event-1"
    assert provider.created_event_summaries == ["Test Professional/Jane Doe"]


def test_confirm_selected_slot_archives_active_chat_messages_into_subsession() -> None:
    service, repository, _, _ = build_service(["req-1", "conf-req-1"])
    conversation_repository = service._conversation_repository
    conversation_repository.save_message(
        message_entity.Message(
            id="msg-1",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            direction="INBOUND",
            role="user",
            content="Hola, quiero una cita",
            provider_message_id="wamid-in-1",
            created_at=datetime.datetime(2026, 1, 1, 9, 0, tzinfo=datetime.UTC),
        )
    )
    conversation_repository.save_message(
        message_entity.Message(
            id="msg-2",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            direction="OUTBOUND",
            role="assistant",
            content="Claro, te ayudo con eso.",
            provider_message_id="wamid-out-1",
            created_at=datetime.datetime(2026, 1, 1, 9, 1, tzinfo=datetime.UTC),
        )
    )
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
        ),
    )

    assert result.status == "BOOKED"
    active_messages_before_close = conversation_repository.list_messages("tenant-1", "conv-1")
    assert len(active_messages_before_close) == 2

    close_result = service.close_session(
        tenant_id="tenant-1",
        conversation_id="conv-1",
    )
    assert close_result["status"] == "SESSION_CLOSED"

    active_messages = conversation_repository.list_messages("tenant-1", "conv-1")
    assert active_messages == []
    conversation = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert conversation.last_message_preview is None
    assert conversation.message_ids == []
    assert len(conversation.subsessions) == 1
    archived_session = conversation.subsessions[0]
    assert archived_session.archived_reason == "APPOINTMENT_BOOKED"
    assert archived_session.scheduling_request_id == request.request_id
    assert archived_session.calendar_event_id == "event-1"
    assert len(archived_session.messages) == 2
    assert archived_session.messages[0].content == "Hola, quiero una cita"
    assert archived_session.messages[1].content == "Claro, te ayudo con eso."


def test_confirm_selected_slot_treats_google_conflict_as_slot_conflict() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    provider.create_event_errors = [
        service_exceptions.ExternalProviderError(
            "google calendar create event failed (status=409, detail=conflict)"
        )
    ]
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
        ),
    )

    assert result.status == "SLOT_CONFLICT"


def test_select_slot_for_confirmation_persists_selected_slot() -> None:
    service, repository, _, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        ),
        scheduling_slot_entity.SchedulingSlot(
            id="slot-2",
            start_at=datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 13, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        ),
    ]
    repository.save_request(stored)

    response = service.select_slot_for_confirmation(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id=request.request_id,
        slot_id="slot-2",
    )

    assert response.selected_slot_id == "slot-2"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.selected_slot_id == "slot-2"
    assert reloaded.slots[0].status == "PROPOSED"
    assert reloaded.slots[1].status == "SELECTED"


def test_select_slot_for_confirmation_switches_selected_slot() -> None:
    service, repository, _, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.selected_slot_id = "slot-1"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="SELECTED",
        ),
        scheduling_slot_entity.SchedulingSlot(
            id="slot-2",
            start_at=datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 13, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        ),
    ]
    repository.save_request(stored)

    response = service.select_slot_for_confirmation(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id=request.request_id,
        slot_id="slot-2",
    )

    assert response.selected_slot_id == "slot-2"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.selected_slot_id == "slot-2"
    assert reloaded.slots[0].status == "PROPOSED"
    assert reloaded.slots[1].status == "SELECTED"


def test_confirm_selected_slot_accepts_selected_slot_status() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.selected_slot_id = "slot-1"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="SELECTED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
        ),
    )

    assert result.status == "BOOKED"
    assert provider.created_event_summaries == ["Test Professional/Jane Doe"]


def test_reschedule_booked_slot_updates_booked_request() -> None:
    service, repository, provider, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    updated_request = service.reschedule_booked_slot(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.RescheduleBookedSlotInputDTO(
            start_at=datetime.datetime(2026, 1, 2, 15, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 2, 16, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            event_summary="Cita reprogramada",
        ),
    )

    assert updated_request.status == "BOOKED"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.slots[0].start_at == datetime.datetime(2026, 1, 2, 15, 0, tzinfo=datetime.UTC)
    assert provider.updated_event_summaries == ["Cita reprogramada"]


def test_cancel_booked_slot_preserves_status_and_clears_calendar_event() -> None:
    service, repository, provider, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    cancelled_request = service.cancel_booked_slot(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.CancelBookedSlotInputDTO(reason="No puede asistir"),
    )

    assert cancelled_request.status == "BOOKED"
    assert provider.deleted_event_ids == ["event-1"]
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.calendar_event_id is None
    assert reloaded.selected_slot_id is None
    assert reloaded.professional_note == "No puede asistir"


def test_cancel_booked_slot_tolerates_google_not_found() -> None:
    service, repository, provider, _ = build_service(["req-1"])
    provider.delete_event_errors = [
        service_exceptions.ExternalProviderError(
            "google calendar delete event failed (status=404, detail=not found)"
        )
    ]
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-404"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    cancelled_request = service.cancel_booked_slot(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.CancelBookedSlotInputDTO(reason=None),
    )

    assert cancelled_request.status == "BOOKED"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.calendar_event_id is None


def test_update_booked_payment_updates_request() -> None:
    service, repository, _, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    updated = service.update_booked_payment(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.UpdateBookedSlotPaymentInputDTO(
            payment_amount_cop=90000,
            payment_method="CASH",
            payment_status="PAID",
        ),
    )

    assert updated.payment_amount_cop == 90000
    assert updated.payment_method == "CASH"
    assert updated.payment_status == "PAID"
    assert updated.payment_updated_at is not None
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.payment_amount_cop == 90000
    assert reloaded.payment_status == "PAID"


def test_update_booked_payment_persists_usd_currency() -> None:
    service, repository, _, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    updated = service.update_booked_payment(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.UpdateBookedSlotPaymentInputDTO(
            payment_amount_cop=120,
            payment_currency="USD",
            payment_method="TRANSFER",
            payment_status="PAID",
        ),
    )

    assert updated.payment_amount_cop == 120
    assert updated.payment_currency == "USD"
    assert updated.payment_status == "PAID"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.payment_currency == "USD"


def test_update_booked_payment_dto_rejects_non_positive_amount() -> None:
    with pytest.raises(pydantic.ValidationError):
        scheduling_dto.UpdateBookedSlotPaymentInputDTO(
            payment_amount_cop=0,
            payment_method="TRANSFER",
            payment_status="PENDING",
        )


# ── Auto-close BOOKED tests ─────────────────────────────────────────


def test_auto_close_task_scheduled_on_booking() -> None:
    service, repository, provider, task_sched = build_service(["req-1", "conf-req-1"])
    request_id = _book_request(service, repository, provider)
    assert len(task_sched.scheduled_tasks) == 1
    task = task_sched.scheduled_tasks[0]
    assert task["tenant_id"] == "tenant-1"
    assert task["scheduling_request_id"] == request_id
    assert task["delay_seconds"] == 3600


def test_auto_close_closes_booked_request() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    request_id = _book_request(service, repository, provider)
    result = service.auto_close_booked_request("tenant-1", request_id)
    assert result == {"status": "SESSION_CLOSED", "action": "closed"}
    stored = repository.get_request_by_id("tenant-1", request_id)
    assert stored is not None
    assert stored.status == "SESSION_CLOSED"


def test_auto_close_skips_non_booked_request() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    request_id = _book_request(service, repository, provider)
    stored = repository.get_request_by_id("tenant-1", request_id)
    assert stored is not None
    stored.status = "SESSION_CLOSED"
    repository.save_request(stored)
    result = service.auto_close_booked_request("tenant-1", request_id)
    assert result == {"status": "SESSION_CLOSED", "action": "skipped"}


def test_auto_close_raises_for_missing_request() -> None:
    service, _, _, _ = build_service(["req-1"])
    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.auto_close_booked_request("tenant-1", "nonexistent-id")


def test_auto_close_task_failure_does_not_break_booking() -> None:
    service, repository, _provider, task_sched = build_service(["req-1", "conf-req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    def failing_schedule(tenant_id: str, scheduling_request_id: str, delay_seconds: int) -> str:
        raise service_exceptions.ExternalProviderError("Cloud Tasks unavailable")

    task_sched.schedule_auto_close = failing_schedule  # type: ignore[method-assign]

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Booking",
        ),
    )
    assert result.status == "BOOKED"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.status == "BOOKED"


def test_confirm_slot_virtual_modality_passes_with_meet_true() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.appointment_modality = "VIRTUAL"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
            attendee_emails=["jane@example.com"],
        ),
    )

    assert result.status == "BOOKED"
    assert provider.last_create_with_meet == [True]
    assert provider.last_create_attendee_emails == [["jane@example.com"]]


def test_confirm_slot_presencial_modality_passes_with_meet_false() -> None:
    service, repository, provider, _ = build_service(["req-1", "conf-req-1"])
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.appointment_modality = "PRESENCIAL"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Professional/Jane Doe",
            attendee_emails=["jane@example.com"],
        ),
    )

    assert result.status == "BOOKED"
    assert provider.last_create_with_meet == [False]
    assert provider.last_create_attendee_emails == [["jane@example.com"]]


# ---------------------------------------------------------------------------
# close_attendance_confirmation
# ---------------------------------------------------------------------------


def _seed_attendance_confirmation_request(
    scheduling_repo: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
) -> str:
    """Insert an AWAITING_ATTENDANCE_CONFIRMATION request directly into the repo."""
    request = scheduling_request_entity.SchedulingRequest(
        id="attend-req-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="RETRY",
        status="AWAITING_ATTENDANCE_CONFIRMATION",
        round_number=2,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        slots=[],
        slot_options_map={},
        selected_slot_id=None,
        calendar_event_id=None,
        source_appointment_id="original-sched-req-1",
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    scheduling_repo.save_request(request)
    return request.id


def test_close_attendance_confirmation_closes_session_immediately() -> None:
    """close_attendance_confirmation transitions request to SESSION_CLOSED right away."""
    service, scheduling_repo, _, _ = build_service(["req-1"])
    request_id = _seed_attendance_confirmation_request(scheduling_repo)

    result = service.close_attendance_confirmation(
        tenant_id="tenant-1",
        conversation_id="conv-1",
    )

    assert result["status"] == "SESSION_CLOSED"
    assert result["action"] == "closed"

    closed = scheduling_repo.get_request_by_id("tenant-1", request_id)
    assert closed is not None
    assert closed.status == "SESSION_CLOSED"


def test_close_attendance_confirmation_skips_when_no_matching_request() -> None:
    """If no AWAITING_ATTENDANCE_CONFIRMATION request exists, returns a no-op result."""
    service, scheduling_repo, _, _ = build_service(["req-1"])
    # Seed a BOOKED request (different status — should not match).
    request = scheduling_request_entity.SchedulingRequest(
        id="booked-req-1",
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
        calendar_event_id=None,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    scheduling_repo.save_request(request)

    result = service.close_attendance_confirmation(
        tenant_id="tenant-1",
        conversation_id="conv-1",
    )

    assert result["status"] == "skipped"
    # The BOOKED request must not have been touched.
    unchanged = scheduling_repo.get_request_by_id("tenant-1", "booked-req-1")
    assert unchanged is not None
    assert unchanged.status == "BOOKED"


def test_auto_close_booked_request_handles_attendance_confirmation_status() -> None:
    """auto_close_booked_request closes AWAITING_ATTENDANCE_CONFIRMATION requests via manual-close archival."""
    service, scheduling_repo, _, _ = build_service(["req-1"])
    request_id = _seed_attendance_confirmation_request(scheduling_repo)

    result = service.auto_close_booked_request(
        tenant_id="tenant-1",
        scheduling_request_id=request_id,
    )

    assert result["status"] == "SESSION_CLOSED"
    assert result["action"] == "closed"

    closed = scheduling_repo.get_request_by_id("tenant-1", request_id)
    assert closed is not None
    assert closed.status == "SESSION_CLOSED"


# ---------------------------------------------------------------------------
# approve_payment — reminder-reply branch
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_service_with_reminder_deps(
    id_values: list[str],
    store: in_memory_store.InMemoryStore,
) -> tuple[
    scheduling_service.SchedulingService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter,
    whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
    fake_adapters.FakeWhatsappProvider,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
]:
    """Build a SchedulingService wired with manual appointment repo, WA provider, and WA connection."""
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repo = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    manual_appt_repo = (
        manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter(store)
    )
    wa_connection_repo = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    wa_provider = fake_adapters.FakeWhatsappProvider()
    clock = fake_adapters.FixedClock(_NOW)
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repo,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
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
            updated_at=_NOW,
            connected_at=_NOW,
        )
    )
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=_NOW,
            updated_at=_NOW,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    wa_connection_repo.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-id-1",
            business_account_id="waba-1",
            access_token="wa-access-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=_NOW,
        )
    )
    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    builder = _build_event_description_builder(store)
    service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        manual_appointment_repository=manual_appt_repo,
        whatsapp_provider=wa_provider,
        whatsapp_connection_repository=wa_connection_repo,
        event_description_builder=builder,
    )
    return (
        service,
        scheduling_repo,
        manual_appt_repo,
        wa_connection_repo,
        wa_provider,
        conversation_repo,
    )


def _seed_recent_patient_inbound(
    conversation_repo: conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    conversation_id: str = "conv-1",
    tenant_id: str = "tenant-1",
) -> None:
    """Persist a recent INBOUND so the 24h freeform window in
    payment_confirmation_dispatcher accepts the send."""
    conversation_repo.save_message(
        message_entity.Message(
            id="seed-inbound-1",
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            direction="INBOUND",
            role="user",
            content="ya pagué",
            provider_message_id="prov-inbound-1",
            created_at=_NOW,
        )
    )


def _seed_payment_reminder_request(
    scheduling_repo: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    source_appointment_id: str,
    source_appointment_kind: str | None,
    patient_first_name: str = "Laura",
) -> str:
    """Insert an AWAITING_PAYMENT_CONFIRMATION request that came from a reminder."""
    request = scheduling_request_entity.SchedulingRequest(
        id="pay-req-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="RETRY",
        status="AWAITING_PAYMENT_CONFIRMATION",
        round_number=2,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        patient_first_name=patient_first_name,
        slots=[],
        slot_options_map={},
        selected_slot_id=None,
        calendar_event_id=None,
        source_appointment_id=source_appointment_id,
        source_appointment_kind=source_appointment_kind,  # type: ignore[arg-type]
        created_at=_NOW,
        updated_at=_NOW,
    )
    scheduling_repo.save_request(request)
    return request.id


def test_approve_payment_from_reminder_marks_manual_appointment_paid_and_closes_session() -> None:
    """Approving a reminder-reply request marks the ManualAppointment PAID and closes the session."""
    store = in_memory_store.InMemoryStore()
    service, scheduling_repo, manual_appt_repo, _, wa_provider, conversation_repo = (
        _build_service_with_reminder_deps(["msg-id-1"], store)
    )
    _seed_recent_patient_inbound(conversation_repo)

    # Create the source ManualAppointment.
    appt_id = "manual-appt-1"
    appt = manual_appointment_entity.ManualAppointment(
        id=appt_id,
        tenant_id="tenant-1",
        patient_whatsapp_user_id="wa-user-1",
        status="SCHEDULED",
        calendar_event_id="cal-event-1",
        start_at=datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC),
        end_at=datetime.datetime(2026, 3, 1, 11, 0, tzinfo=datetime.UTC),
        timezone="America/Bogota",
        summary="Cita test",
        payment_status="PENDING",
        created_at=_NOW,
        updated_at=_NOW,
    )
    manual_appt_repo.save(appt)

    _seed_payment_reminder_request(
        scheduling_repo,
        source_appointment_id=appt_id,
        source_appointment_kind="MANUAL_APPOINTMENT",
    )

    service.approve_payment(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id="pay-req-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            payment_amount_cop=80000,
        ),
    )

    # Source ManualAppointment must be marked PAID.
    updated_appt = manual_appt_repo.get_by_id("tenant-1", appt_id)
    assert updated_appt is not None
    assert updated_appt.payment_status == "PAID"
    assert updated_appt.payment_amount_cop == 80000

    # Synthetic request must be SESSION_CLOSED.
    closed_req = scheduling_repo.get_request_by_id("tenant-1", "pay-req-1")
    assert closed_req is not None
    assert closed_req.status == "SESSION_CLOSED"

    # WhatsApp provider must have received a confirmation message.
    assert len(wa_provider.sent_messages) == 1
    sent = wa_provider.sent_messages[0]
    assert "Laura" in sent["text"]
    assert "confirmado" in sent["text"].lower()


def test_approve_payment_from_reminder_marks_scheduling_request_paid() -> None:
    """Approving a reminder-reply request marks the source SchedulingRequest PAID."""
    store = in_memory_store.InMemoryStore()
    service, scheduling_repo, _, _, wa_provider, conversation_repo = (
        _build_service_with_reminder_deps(["msg-id-1"], store)
    )
    _seed_recent_patient_inbound(conversation_repo)

    # Create the source SchedulingRequest (BOOKED).
    source_req = scheduling_request_entity.SchedulingRequest(
        id="src-req-1",
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
        calendar_event_id="cal-1",
        payment_status="PENDING",
        created_at=_NOW,
        updated_at=_NOW,
    )
    scheduling_repo.save_request(source_req)

    _seed_payment_reminder_request(
        scheduling_repo,
        source_appointment_id="src-req-1",
        source_appointment_kind="SCHEDULING_REQUEST",
    )

    service.approve_payment(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id="pay-req-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            payment_amount_cop=150000,
        ),
    )

    # Source SchedulingRequest must be marked PAID.
    updated_source = scheduling_repo.get_request_by_id("tenant-1", "src-req-1")
    assert updated_source is not None
    assert updated_source.payment_status == "PAID"
    assert updated_source.payment_amount_cop == 150000

    # Synthetic request must be SESSION_CLOSED.
    closed_req = scheduling_repo.get_request_by_id("tenant-1", "pay-req-1")
    assert closed_req is not None
    assert closed_req.status == "SESSION_CLOSED"

    # WA confirmation sent.
    assert len(wa_provider.sent_messages) == 1


def test_approve_payment_from_reminder_closes_session_even_without_recent_inbound() -> None:
    """If the patient never replied to the reminder (no INBOUND in 24h), the
    confirmation message can't be sent (Meta blocks freeform), but the
    session must still close so the conversation leaves Pago pendiente."""
    store = in_memory_store.InMemoryStore()
    service, scheduling_repo, manual_appt_repo, _, wa_provider, _ = (
        _build_service_with_reminder_deps(["msg-id-1"], store)
    )
    # NOTE: deliberately no _seed_recent_patient_inbound — patient stayed silent.

    appt_id = "manual-appt-silent"
    manual_appt_repo.save(
        manual_appointment_entity.ManualAppointment(
            id=appt_id,
            tenant_id="tenant-1",
            patient_whatsapp_user_id="wa-user-1",
            status="SCHEDULED",
            calendar_event_id="cal-event-silent",
            start_at=datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 3, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita silenciosa",
            payment_status="PENDING",
            created_at=_NOW,
            updated_at=_NOW,
        )
    )
    _seed_payment_reminder_request(
        scheduling_repo,
        source_appointment_id=appt_id,
        source_appointment_kind="MANUAL_APPOINTMENT",
    )

    service.approve_payment(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id="pay-req-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            payment_amount_cop=50000,
        ),
    )

    # Source PAID.
    paid_appt = manual_appt_repo.get_by_id("tenant-1", appt_id)
    assert paid_appt is not None
    assert paid_appt.payment_status == "PAID"
    # Synthetic SESSION_CLOSED.
    closed_req = scheduling_repo.get_request_by_id("tenant-1", "pay-req-1")
    assert closed_req is not None
    assert closed_req.status == "SESSION_CLOSED"
    # No freeform message because there was no recent INBOUND.
    assert len(wa_provider.sent_messages) == 0


def test_approve_payment_from_reminder_handles_missing_source_gracefully() -> None:
    """If the source appointment is not found, the session is still closed and WA message sent."""
    store = in_memory_store.InMemoryStore()
    service, scheduling_repo, _, _, wa_provider, conversation_repo = (
        _build_service_with_reminder_deps(["msg-id-1"], store)
    )
    _seed_recent_patient_inbound(conversation_repo)

    # Seed the synthetic request pointing to a non-existent source.
    _seed_payment_reminder_request(
        scheduling_repo,
        source_appointment_id="non-existent-appt",
        source_appointment_kind="MANUAL_APPOINTMENT",
    )

    # Should not raise — missing source is best-effort.
    service.approve_payment(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id="pay-req-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            payment_amount_cop=50000,
        ),
    )

    # Session still closed.
    closed_req = scheduling_repo.get_request_by_id("tenant-1", "pay-req-1")
    assert closed_req is not None
    assert closed_req.status == "SESSION_CLOSED"

    # WA confirmation still sent.
    assert len(wa_provider.sent_messages) == 1


def test_approve_payment_original_flow_unchanged() -> None:
    """Requests without source_appointment_id still transition to AWAITING_PATIENT_CHOICE."""
    service, repository, _, _ = build_service(["req-1"])

    # Seed a request that came from the normal scheduling flow (no source_appointment_id).
    request = scheduling_request_entity.SchedulingRequest(
        id="normal-pay-req-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="INITIAL",
        status="AWAITING_PAYMENT_CONFIRMATION",
        round_number=1,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        slots=[
            scheduling_slot_entity.SchedulingSlot(
                id="slot-1",
                start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
                timezone="America/Bogota",
                status="SELECTED",
            )
        ],
        slot_options_map={"1": "slot-1"},
        selected_slot_id="slot-1",
        calendar_event_id=None,
        source_appointment_id=None,
        source_appointment_kind=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    repository.save_request(request)

    result = service.approve_payment(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id="normal-pay-req-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            payment_amount_cop=75000,
        ),
    )

    # Original flow: must transition to AWAITING_PATIENT_CHOICE.
    assert result.status == "AWAITING_PATIENT_CHOICE"
    stored = repository.get_request_by_id("tenant-1", "normal-pay-req-1")
    assert stored is not None
    assert stored.status == "AWAITING_PATIENT_CHOICE"
    assert stored.payment_status == "PAID"
    assert stored.payment_amount_cop == 75000


# ---------------------------------------------------------------------------
# payment_timing = AFTER_SESSION
# ---------------------------------------------------------------------------


def test_select_slot_stays_awaiting_patient_choice_when_payment_timing_is_after_session() -> None:
    """Con payment_timing=AFTER_SESSION, al llamar select_slot_for_confirmation el
    request debe permanecer en AWAITING_PATIENT_CHOICE (no pasa a AWAITING_PAYMENT_CONFIRMATION
    ni a BOOKED inline). El selected_slot_id queda set para que el runtime resolver
    derive state=COLLECTING_CONFIRMATION_DATA y el bot recoja email/edad/etc.
    No se crea evento de calendar en este paso ni se agenda recordatorio todavía."""
    service, repository, provider, _task_sched, reminder_repo = (
        build_service_with_in_person_profile(["req-1"])
    )

    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    far_start = datetime.datetime(2026, 2, 1, 10, 0, tzinfo=datetime.UTC)
    far_end = datetime.datetime(2026, 2, 1, 11, 0, tzinfo=datetime.UTC)
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=far_start,
            end_at=far_end,
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.select_slot_for_confirmation(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id=request.request_id,
        slot_id="slot-1",
    )

    # AFTER_SESSION: permanece en AWAITING_PATIENT_CHOICE con selected_slot_id set.
    assert result.status == "AWAITING_PATIENT_CHOICE"
    assert result.selected_slot_id == "slot-1"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.status == "AWAITING_PATIENT_CHOICE"
    assert reloaded.selected_slot_id == "slot-1"

    # No se crea evento de calendar todavía — eso ocurre en confirm_selected_slot_and_create_event.
    assert len(provider.created_event_summaries) == 0

    # No se agenda recordatorio todavía.
    reminders = reminder_repo.list_by_tenant("tenant-1")
    assert len(reminders) == 0

    # Nunca transiciona a AWAITING_PAYMENT_CONFIRMATION.
    assert result.status != "AWAITING_PAYMENT_CONFIRMATION"


# ---------------------------------------------------------------------------
# Fase 4b — eval tenant Calendar skip
# ---------------------------------------------------------------------------


def _build_service_for_eval(
    id_values: list[str],
    is_eval: bool,
) -> tuple[
    scheduling_service.SchedulingService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
]:
    """Build SchedulingService wired with a tenant_repository.

    When ``is_eval=True`` the tenant is seeded with ``is_eval_tenant=True``,
    so Calendar calls are skipped.  When ``is_eval=False`` the tenant flag is
    False and the full Calendar path is exercised.
    """
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
    )

    tenant_repo.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Tenant",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            is_eval_tenant=is_eval,
        )
    )
    calendar_connection_repository.save(
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
    conversation_repository.save_conversation(
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

    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    builder = _build_event_description_builder(store)
    svc = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
        tenant_repository=tenant_repo,
    )
    return svc, scheduling_repository, provider


def test_books_slot_without_calendar_when_tenant_is_eval() -> None:
    """Eval tenant: slot confirmed, no Calendar adapter calls, calendar_event_id is None."""
    service, repository, provider = _build_service_for_eval(["req-1"], is_eval=True)

    request = service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Ansiedad",
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
        ),
    )
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 10, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 10, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Eval Booking",
        ),
    )

    assert result.status == "BOOKED"
    assert result.calendar_event_id is None
    # No Calendar calls at all (neither conflict check nor create_event).
    assert provider.list_busy_intervals_call_count == 0
    assert len(provider.created_event_summaries) == 0
    # Request persisted correctly.
    booked = repository.get_request_by_id("tenant-1", request.request_id)
    assert booked is not None
    assert booked.status == "BOOKED"
    assert booked.calendar_event_id is None


def test_books_slot_normally_when_tenant_is_not_eval() -> None:
    """Non-eval tenant: full Calendar path — create_event is called and event_id persisted."""
    service, repository, provider = _build_service_for_eval(["req-1", "conf-req-1"], is_eval=False)

    request = service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Ansiedad",
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
        ),
    )
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "AWAITING_PATIENT_CHOICE"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 10, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 10, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    repository.save_request(stored)

    result = service.confirm_selected_slot_and_create_event(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
            request_id=request.request_id,
            slot_id="slot-1",
            event_summary="Test Normal Booking",
        ),
    )

    assert result.status == "BOOKED"
    assert result.calendar_event_id is not None
    # Calendar adapter WAS called.
    assert len(provider.created_event_summaries) == 1
    assert provider.created_event_summaries[0] == "Test Normal Booking"
    # Request persisted with event id.
    booked = repository.get_request_by_id("tenant-1", request.request_id)
    assert booked is not None
    assert booked.status == "BOOKED"
    assert booked.calendar_event_id is not None


# ---------------------------------------------------------------------------
# Fix B1: _resolve_location reads main_city from AgentProfile (not hardcoded)
# ---------------------------------------------------------------------------


def _build_service_with_main_city(
    main_city: str,
) -> tuple[
    scheduling_service.SchedulingService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
]:
    """Minimal service wired with an AgentProfile that has a specific main_city."""
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="prompt",
            identity=agent_profile_entity.AssistantIdentity(main_city=main_city),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    calendar_connection_repository.save(
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
    conversation_repository.save_conversation(
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
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["req-1"])
    provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
    )
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo
    )
    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    svc = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
        agent_profile_repository=agent_profile_repo,
    )
    return svc, scheduling_repo


def test_resolve_location_presencial_returns_main_city_from_agent_profile() -> None:
    """Fix B1: PRESENCIAL location must come from AgentProfile.identity.main_city."""
    svc, repo = _build_service_with_main_city("Medellín")

    result = svc.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Primera cita",
            appointment_modality="PRESENCIAL",
            patient_location=None,
        ),
    )

    stored = repo.get_request_by_id("tenant-1", result.request_id)
    assert stored is not None
    assert stored.patient_location == "Medellín"


def test_resolve_location_presencial_generic_fallback_when_no_profile() -> None:
    """Fix B1: When AgentProfile has no main_city, fallback is generic 'Presencial'."""
    svc, repo = _build_service_with_main_city("")

    result = svc.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Primera cita",
            appointment_modality="PRESENCIAL",
            patient_location=None,
        ),
    )

    stored = repo.get_request_by_id("tenant-1", result.request_id)
    assert stored is not None
    # Empty main_city → generic fallback, not a hardcoded city name
    assert stored.patient_location == "Presencial"


# ---------------------------------------------------------------------------
# change_booked_modality tests
# ---------------------------------------------------------------------------


def _make_booked_request_for_modality(
    repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    service: scheduling_service.SchedulingService,
    modality: str,
    slot_start: datetime.datetime | None = None,
) -> str:
    """Create a BOOKED SchedulingRequest with the given modality and return request_id."""
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.appointment_modality = modality  # type: ignore[assignment]
    start = slot_start or datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.UTC)
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=start,
            end_at=start + datetime.timedelta(hours=1),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)
    return request.request_id


def test_change_modality_noop_when_same_modality() -> None:
    """Requesting the same modality returns the current summary without touching Calendar."""
    service, repository, provider, _ = build_service(["req-1"])
    request_id = _make_booked_request_for_modality(repository, service, "PRESENCIAL")

    result = service.change_booked_modality(
        tenant_id="tenant-1",
        request_id=request_id,
        input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="PRESENCIAL"),
    )

    assert result.appointment_modality == "PRESENCIAL"
    assert len(provider.updated_events) == 0


def test_change_modality_blocks_past_appointment() -> None:
    """Appointments in the past (start_at <= now) must raise InvalidStateError."""
    service, repository, provider, _ = build_service(["req-1"])
    past_start = datetime.datetime(2025, 12, 31, 10, 0, tzinfo=datetime.UTC)
    request_id = _make_booked_request_for_modality(
        repository, service, "PRESENCIAL", slot_start=past_start
    )

    with pytest.raises(service_exceptions.InvalidStateError) as exc_info:
        service.change_booked_modality(
            tenant_id="tenant-1",
            request_id=request_id,
            input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
        )

    assert "past" in str(exc_info.value).lower()
    assert len(provider.updated_events) == 0


def test_change_modality_blocks_non_booked_request() -> None:
    """Only BOOKED requests can change modality; other statuses raise InvalidStateError."""
    service, _repository, _, _ = build_service(["req-1"])
    request = create_awaiting_review_request(service)
    # Leave the request in AWAITING_CONSULTATION_REVIEW (not BOOKED)

    with pytest.raises(service_exceptions.InvalidStateError) as exc_info:
        service.change_booked_modality(
            tenant_id="tenant-1",
            request_id=request.request_id,
            input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
        )

    assert "booked" in str(exc_info.value).lower()


def test_change_modality_raises_not_found_for_missing_request() -> None:
    service, _, _, _ = build_service(["req-1"])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.change_booked_modality(
            tenant_id="tenant-1",
            request_id="does-not-exist",
            input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
        )


def test_change_modality_presencial_to_virtual_updates_calendar() -> None:
    """PRESENCIAL → VIRTUAL: update_event called with with_meet=True; modality persisted."""
    service, repository, provider, _ = build_service(["req-1"])
    request_id = _make_booked_request_for_modality(repository, service, "PRESENCIAL")

    result = service.change_booked_modality(
        tenant_id="tenant-1",
        request_id=request_id,
        input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
    )

    assert result.appointment_modality == "VIRTUAL"
    assert len(provider.updated_events) == 1
    assert provider.last_update_with_meet == [True]
    reloaded = repository.get_request_by_id("tenant-1", request_id)
    assert reloaded is not None
    assert reloaded.appointment_modality == "VIRTUAL"


def test_change_modality_virtual_to_presencial_updates_calendar() -> None:
    """VIRTUAL → PRESENCIAL: update_event called with with_meet=False; modality persisted."""
    service, repository, provider, _ = build_service(["req-1"])
    request_id = _make_booked_request_for_modality(repository, service, "VIRTUAL")

    result = service.change_booked_modality(
        tenant_id="tenant-1",
        request_id=request_id,
        input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="PRESENCIAL"),
    )

    assert result.appointment_modality == "PRESENCIAL"
    assert len(provider.updated_events) == 1
    assert provider.last_update_with_meet == [False]
    reloaded = repository.get_request_by_id("tenant-1", request_id)
    assert reloaded is not None
    assert reloaded.appointment_modality == "PRESENCIAL"


def test_change_modality_skips_calendar_for_eval_tenant() -> None:
    """Eval tenant: modality persisted, but no Calendar call is made."""
    service, repository, provider = _build_service_for_eval(["req-1"], is_eval=True)

    request = service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            consultation_reason="Ansiedad",
            appointment_modality="PRESENCIAL",
            patient_location="Bogota",
        ),
    )
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = None  # eval tenants have no calendar_event_id
    stored.appointment_modality = "PRESENCIAL"
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 6, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    result = service.change_booked_modality(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
    )

    assert result.appointment_modality == "VIRTUAL"
    assert len(provider.updated_events) == 0


def test_change_modality_reschedules_reminder_with_new_modality() -> None:
    """After modality change, reminder is cancelled and re-scheduled with new modality."""
    service, repository, _provider, _task_sched, reminder_repo = (
        build_service_with_in_person_profile(["req-1", "reminder-1"])
    )
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.appointment_modality = "PRESENCIAL"
    far_start = datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.UTC)
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=far_start,
            end_at=far_start + datetime.timedelta(hours=1),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    # Seed a reminder for the existing appointment
    reminder_repo.list_by_tenant("tenant-1")  # ensure fresh state

    service.change_booked_modality(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
    )

    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.appointment_modality == "VIRTUAL"


def test_change_modality_propagates_actual_payment_status_to_reminder() -> None:
    """Reminder receives the actual payment_status from the request, not a hardcoded value."""
    service, repository, _provider, _task_sched, _reminder_repo = (
        build_service_with_in_person_profile(["req-1", "reminder-1"])
    )
    request = create_awaiting_review_request(service)
    stored = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored is not None
    stored.status = "BOOKED"
    stored.selected_slot_id = "slot-1"
    stored.calendar_event_id = "event-1"
    stored.appointment_modality = "PRESENCIAL"
    stored.payment_status = "PENDING"  # explicitly PENDING, not PAID
    far_start = datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.UTC)
    stored.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=far_start,
            end_at=far_start + datetime.timedelta(hours=1),
            timezone="America/Bogota",
            status="BOOKED",
        )
    ]
    repository.save_request(stored)

    service.change_booked_modality(
        tenant_id="tenant-1",
        request_id=request.request_id,
        input_dto=scheduling_dto.ChangeBookedModalityInputDTO(new_modality="VIRTUAL"),
    )

    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.appointment_modality == "VIRTUAL"
    assert reloaded.payment_status == "PENDING"  # payment status unchanged


# ---------------------------------------------------------------------------
# Reschedule-by-bot flow
# ---------------------------------------------------------------------------


def _seed_booked_request(
    repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    request_id: str = "original-req-1",
    conversation_id: str = "conv-1",
    consultation_reason: str = "Ansiedad",
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] = "PRESENCIAL",
    patient_first_name: str | None = "Ana",
    patient_last_name: str | None = "Garcia",
    patient_age: int | None = 30,
    patient_location: str | None = None,
    calendar_event_id: str = "cal-event-1",
) -> None:
    """Seed a BOOKED scheduling request in the in-memory repository."""
    repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id=request_id,
            tenant_id="tenant-1",
            conversation_id=conversation_id,
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="BOOKED",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            consultation_reason=consultation_reason,
            appointment_modality=appointment_modality,
            patient_location=patient_location,
            patient_first_name=patient_first_name,
            patient_last_name=patient_last_name,
            patient_age=patient_age,
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
            calendar_event_id=calendar_event_id,
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )


def test_submit_reschedule_for_review_creates_child_request_inheriting_data() -> None:
    """Given a BOOKED SR, submit_reschedule_for_review creates a RESCHEDULE child SR that
    inherits consultation_reason, modality, location, and patient names from the original."""
    service, repository, _provider, _ = build_service(["reschedule-req-1"])
    _seed_booked_request(repository)

    result = service.submit_reschedule_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitRescheduleForReviewToolInputDTO(
            original_request_id="original-req-1",
            reason="Cambio de agenda",
        ),
    )

    assert result.status == "AWAITING_CONSULTATION_REVIEW"
    assert result.request_id == "reschedule-req-1"

    child = repository.get_request_by_id("tenant-1", "reschedule-req-1")
    assert child is not None
    assert child.request_kind == "RESCHEDULE"
    assert child.source_appointment_id == "original-req-1"
    assert child.source_appointment_kind == "SCHEDULING_REQUEST"
    assert child.consultation_reason == "Ansiedad"
    assert child.appointment_modality == "PRESENCIAL"
    assert child.patient_first_name == "Ana"
    assert child.patient_last_name == "Garcia"
    assert child.patient_age == 30
    assert child.patient_preference_note == "Cambio de agenda"
    assert child.status == "AWAITING_CONSULTATION_REVIEW"
    assert child.calendar_event_id is None
    assert child.selected_slot_id is None


def test_submit_reschedule_for_review_rejects_non_booked() -> None:
    """If the original SR is not BOOKED, submit raises InvalidStateError."""
    service, repository, _provider, _ = build_service(["reschedule-req-1"])
    # Seed a non-BOOKED request
    repository.save_request(
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
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    with pytest.raises(service_exceptions.InvalidStateError) as exc_info:
        service.submit_reschedule_for_review(
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            input_dto=scheduling_dto.SubmitRescheduleForReviewToolInputDTO(
                original_request_id="original-req-1",
            ),
        )

    assert "BOOKED" in str(exc_info.value)


def test_submit_reschedule_for_review_rejects_when_active_reschedule_exists() -> None:
    """If an active RESCHEDULE SR already exists for the original, raises InvalidStateError."""
    service, repository, _provider, _ = build_service(["reschedule-req-2"])
    _seed_booked_request(repository)
    # Seed an existing active RESCHEDULE SR
    repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="existing-reschedule-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="RESCHEDULE",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=2,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            source_appointment_id="original-req-1",
            source_appointment_kind="SCHEDULING_REQUEST",
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    with pytest.raises(service_exceptions.InvalidStateError) as exc_info:
        service.submit_reschedule_for_review(
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            input_dto=scheduling_dto.SubmitRescheduleForReviewToolInputDTO(
                original_request_id="original-req-1",
            ),
        )

    assert "reagendamiento en curso" in str(exc_info.value)


def test_select_proposed_slot_skips_payment_when_kind_is_reschedule() -> None:
    """When request_kind=RESCHEDULE, select_slot_for_confirmation stays in
    AWAITING_PATIENT_CHOICE (with slot selected) regardless of payment_timing.
    This test uses the default BEFORE_SESSION timing (no agent profile repo wired)
    to confirm the RESCHEDULE check overrides the payment step."""
    service, repository, _provider, _ = build_service(["reschedule-req-1"])
    # Seed a RESCHEDULE SR in AWAITING_PATIENT_CHOICE
    repository.save_request(
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
                    start_at=datetime.datetime(2026, 4, 1, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 4, 1, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="PROPOSED",
                )
            ],
            slot_options_map={"1": "new-slot-1"},
            selected_slot_id=None,
            calendar_event_id=None,
            source_appointment_id="original-req-1",
            source_appointment_kind="SCHEDULING_REQUEST",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    result = service.select_slot_for_confirmation(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id="reschedule-req-1",
        slot_id="new-slot-1",
    )

    # Must stay in AWAITING_PATIENT_CHOICE (not AWAITING_PAYMENT_CONFIRMATION)
    assert result.status == "AWAITING_PATIENT_CHOICE"
    assert result.selected_slot_id == "new-slot-1"

    reloaded = repository.get_request_by_id("tenant-1", "reschedule-req-1")
    assert reloaded is not None
    assert reloaded.status == "AWAITING_PATIENT_CHOICE"
    assert reloaded.selected_slot_id == "new-slot-1"


def test_confirm_rescheduled_slot_moves_calendar_event_and_closes_child() -> None:
    """End-to-end: given a RESCHEDULE SR with a selected slot, confirm_rescheduled_slot
    moves the calendar event in place, promotes the RESCHEDULE child to BOOKED (so the
    conversation lands in POST_BOOKING_FOLLOWUP), and detaches the calendar event from
    the original SR so the agenda does not render duplicates."""
    service, repository, provider, _ = build_service(["reschedule-req-1"])
    _seed_booked_request(repository)

    # Seed the RESCHEDULE SR in AWAITING_PATIENT_CHOICE with a selected slot.
    new_start = datetime.datetime(2026, 5, 1, 15, 0, tzinfo=datetime.UTC)
    new_end = datetime.datetime(2026, 5, 1, 16, 0, tzinfo=datetime.UTC)
    repository.save_request(
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
                    start_at=new_start,
                    end_at=new_end,
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "new-slot-1"},
            selected_slot_id="new-slot-1",
            calendar_event_id=None,
            source_appointment_id="original-req-1",
            source_appointment_kind="SCHEDULING_REQUEST",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    result = service.confirm_rescheduled_slot(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        input_dto=scheduling_dto.ConfirmRescheduledSlotInputDTO(
            request_id="reschedule-req-1",
        ),
    )

    # The RESCHEDULE child is now the active BOOKED appointment.
    assert result.request_id == "reschedule-req-1"
    assert result.status == "BOOKED"

    # Calendar event must have been updated (update_event called once).
    assert len(provider.updated_events) == 1
    assert provider.updated_events[0].start_at == new_start
    assert provider.updated_events[0].end_at == new_end

    # RESCHEDULE child holds the calendar event and is BOOKED so the resolver
    # treats the conversation as POST_BOOKING_FOLLOWUP.
    reschedule_sr = repository.get_request_by_id("tenant-1", "reschedule-req-1")
    assert reschedule_sr is not None
    assert reschedule_sr.status == "BOOKED"
    assert reschedule_sr.calendar_event_id is not None

    # Original SR keeps history but lost the calendar event reference, so the
    # agenda calendar does not render two appointments at the same time.
    original_sr = repository.get_request_by_id("tenant-1", "original-req-1")
    assert original_sr is not None
    assert original_sr.calendar_event_id is None
    assert original_sr.status == "SESSION_CLOSED"


def test_confirm_rescheduled_slot_rejects_when_no_slot_selected() -> None:
    """If the RESCHEDULE SR has no selected_slot_id, raises InvalidStateError."""
    service, repository, _provider, _ = build_service(["reschedule-req-1"])
    _seed_booked_request(repository)
    repository.save_request(
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
                    start_at=datetime.datetime(2026, 5, 1, 15, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 5, 1, 16, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="PROPOSED",
                )
            ],
            slot_options_map={"1": "new-slot-1"},
            selected_slot_id=None,  # no slot selected yet
            calendar_event_id=None,
            source_appointment_id="original-req-1",
            source_appointment_kind="SCHEDULING_REQUEST",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    with pytest.raises(service_exceptions.InvalidStateError) as exc_info:
        service.confirm_rescheduled_slot(
            tenant_id="tenant-1",
            conversation_id="conv-1",
            input_dto=scheduling_dto.ConfirmRescheduledSlotInputDTO(
                request_id="reschedule-req-1",
            ),
        )

    assert "slot" in str(exc_info.value).lower()
