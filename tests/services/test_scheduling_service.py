import datetime

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.message as message_entity
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
            consultation_reason="Ansiedad",
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


def test_request_schedule_approval_reopens_when_patient_rejects_offered_slots() -> None:
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
            patient_preference_note="despues de las 4 pm",
            hard_constraints=[],
            rejection_summary=None,
        ),
    )
    stored_request = repository.get_request_by_id("tenant-1", request.request_id)
    assert stored_request is not None
    stored_request.status = "AWAITING_PATIENT_CHOICE"
    stored_request.slots = [
        scheduling_slot_entity.SchedulingSlot(
            id="slot-1",
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            status="PROPOSED",
        )
    ]
    stored_request.slot_options_map = {"1": "slot-1"}
    repository.save_request(stored_request)

    reopened = service.request_schedule_approval(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        input_dto=scheduling_dto.RequestScheduleApprovalInputDTO(
            request_id=request.request_id,
            appointment_modality="VIRTUAL",
            patient_location=None,
            patient_preference_note="no puedo a las 4 pm, prefiero despues de las 6 pm",
            hard_constraints=[],
            rejection_summary=None,
        ),
    )

    assert reopened.request_id == request.request_id
    assert reopened.status == "AWAITING_PROFESSIONAL_SLOTS"
    assert reopened.patient_preference_note == "no puedo a las 4 pm, prefiero despues de las 6 pm"
    assert reopened.patient_location == "Bogota"
    assert reopened.selected_slot_id is None
    assert reopened.slot_options_map == {}
    assert reopened.slots == []


def test_submit_consultation_reason_rejects_when_already_approved() -> None:
    service, _, _ = build_service(["req-1"])
    approved_request = create_collecting_preferences_request(service)

    with pytest.raises(service_exceptions.InvalidStateError) as error:
        service.submit_consultation_reason_for_review(
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            input_dto=scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO(
                request_id=approved_request.request_id,
                consultation_reason="Ansiedad laboral",
            ),
        )

    assert "already approved" in str(error.value)


def test_submit_consultation_reason_allows_resubmission_after_more_info_request() -> None:
    service, repository, _ = build_service(["req-1"])
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


def test_confirm_selected_slot_archives_active_chat_messages_into_subsession() -> None:
    service, repository, _ = build_service(["req-1"])
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


def test_reschedule_booked_slot_updates_booked_request() -> None:
    service, repository, provider = build_service(["req-1"])
    request = create_waiting_professional_slots_request(service)
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


def test_cancel_booked_slot_sets_cancelled_and_clears_calendar_event() -> None:
    service, repository, provider = build_service(["req-1"])
    request = create_waiting_professional_slots_request(service)
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

    assert cancelled_request.status == "CANCELLED"
    assert provider.deleted_event_ids == ["event-1"]
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.calendar_event_id is None
    assert reloaded.selected_slot_id is None
    assert reloaded.professional_note == "No puede asistir"


def test_cancel_booked_slot_tolerates_google_not_found() -> None:
    service, repository, provider = build_service(["req-1"])
    provider.delete_event_errors = [
        service_exceptions.ExternalProviderError(
            "google calendar delete event failed (status=404, detail=not found)"
        )
    ]
    request = create_waiting_professional_slots_request(service)
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

    assert cancelled_request.status == "CANCELLED"
    reloaded = repository.get_request_by_id("tenant-1", request.request_id)
    assert reloaded is not None
    assert reloaded.calendar_event_id is None
