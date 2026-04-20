import datetime

import pydantic
import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
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
    service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
    )
    return service, scheduling_repository, provider, task_sched


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
