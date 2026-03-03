import datetime

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters


def build_service(
    id_values: list[str],
) -> tuple[
    scheduling_service.SchedulingService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
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

    service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )
    return service, scheduling_repository, provider


def create_collecting_preferences_request(
    service: scheduling_service.SchedulingService,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    submitted = service.submit_consultation_reason_for_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
            patient_first_name="Jane",
            patient_last_name="Doe",
            patient_age=29,
            consultation_reason="Ansiedad",
            consultation_details="Me cuesta dormir y me siento abrumada.",
        ),
    )
    return service.resolve_consultation_review(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        request_id=submitted.request_id,
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="APPROVE",
            professional_note="Aprobado",
        ),
    )


def create_waiting_professional_slots_request(
    service: scheduling_service.SchedulingService,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    request = create_collecting_preferences_request(service)
    return service.request_schedule_approval(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.RequestScheduleApprovalInputDTO(
            request_id=request.request_id,
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
            patient_preference_note="prefiere en la tarde",
            hard_constraints=["solo tardes"],
            rejection_summary=None,
        ),
    )


def test_request_schedule_approval_creates_pending_request() -> None:
    service, repository, _ = build_service(["req-1"])
    collecting_request = create_collecting_preferences_request(service)
    request = service.request_schedule_approval(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.RequestScheduleApprovalInputDTO(
            request_id=collecting_request.request_id,
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
            patient_preference_note="prefiere en la tarde",
            hard_constraints=["solo tardes"],
            rejection_summary=None,
        ),
    )

    assert request.request_id == "req-1"
    assert request.status == "AWAITING_PROFESSIONAL_SLOTS"
    stored = repository.get_request_by_id("tenant-1", "req-1")
    assert stored is not None


def test_request_schedule_approval_reuses_open_request() -> None:
    service, repository, _ = build_service(["req-1", "req-2"])
    collecting_request = create_collecting_preferences_request(service)
    first_request = service.request_schedule_approval(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.RequestScheduleApprovalInputDTO(
            request_id=collecting_request.request_id,
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
            patient_preference_note="prefiere en la tarde",
            hard_constraints=[],
            rejection_summary=None,
        ),
    )

    second_request = service.request_schedule_approval(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.RequestScheduleApprovalInputDTO(
            request_id=collecting_request.request_id,
            appointment_modality="VIRTUAL",
            patient_location="Bogota",
            patient_preference_note="prefiere virtual",
            hard_constraints=[],
            rejection_summary=None,
        ),
    )

    assert first_request.request_id == "req-1"
    assert second_request.request_id == "req-1"
    stored_requests = repository.list_requests_by_conversation("tenant-1", "conv-1")
    assert len(stored_requests) == 1


def test_confirm_selected_slot_marks_conflict_when_busy() -> None:
    service, repository, provider = build_service(["req-1"])
    provider.busy_intervals = [
        google_calendar_dto.GoogleCalendarBusyIntervalDTO(
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
        )
    ]
    request = create_waiting_professional_slots_request(service)
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
            event_summary="Jane Doe/ Psi. Alejandra Escobar",
        ),
    )

    assert result.status == "SLOT_CONFLICT"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.status == "AWAITING_PROFESSIONAL_SLOTS"


def test_confirm_selected_slot_creates_event_when_available() -> None:
    service, repository, provider = build_service(["req-1"])
    request = create_waiting_professional_slots_request(service)
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
            event_summary="Jane Doe/ Psi. Alejandra Escobar",
        ),
    )

    assert result.status == "BOOKED"
    assert result.calendar_event_id == "event-1"
    assert provider.created_event_summaries == ["Jane Doe/ Psi. Alejandra Escobar"]


def test_confirm_selected_slot_treats_google_conflict_as_slot_conflict() -> None:
    service, repository, provider = build_service(["req-1"])
    provider.create_event_errors = [
        service_exceptions.ExternalProviderError(
            "google calendar create event failed (status=409, detail=conflict)"
        )
    ]
    request = create_waiting_professional_slots_request(service)
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
            event_summary="Jane Doe/ Psi. Alejandra Escobar",
        ),
    )

    assert result.status == "SLOT_CONFLICT"


def test_select_slot_for_confirmation_persists_selected_slot() -> None:
    service, repository, _ = build_service(["req-1"])
    request = create_waiting_professional_slots_request(service)
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
    service, repository, _ = build_service(["req-1"])
    request = create_waiting_professional_slots_request(service)
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
    service, repository, provider = build_service(["req-1"])
    request = create_waiting_professional_slots_request(service)
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
            event_summary="Jane Doe/ Psi. Alejandra Escobar",
        ),
    )

    assert result.status == "BOOKED"
    assert provider.created_event_summaries == ["Jane Doe/ Psi. Alejandra Escobar"]
