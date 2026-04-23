import datetime

import pydantic
import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.manual_appointment_repository_adapter as manual_appointment_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.manual_appointment as manual_appointment_entity
import src.domain.entities.message as message_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
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
    )
    return (
        service,
        scheduling_repo,
        manual_appt_repo,
        wa_connection_repo,
        wa_provider,
        conversation_repo,
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
    service, scheduling_repo, manual_appt_repo, _, wa_provider, _ = (
        _build_service_with_reminder_deps(["msg-id-1"], store)
    )

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
    service, scheduling_repo, _, _, wa_provider, _ = _build_service_with_reminder_deps(
        ["msg-id-1"], store
    )

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


def test_approve_payment_from_reminder_handles_missing_source_gracefully() -> None:
    """If the source appointment is not found, the session is still closed and WA message sent."""
    store = in_memory_store.InMemoryStore()
    service, scheduling_repo, _, _, wa_provider, _ = _build_service_with_reminder_deps(
        ["msg-id-1"], store
    )

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
