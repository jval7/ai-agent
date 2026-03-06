import datetime
import logging

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.conversation_dto as conversation_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.conversation_control_service as conversation_control_service
import tests.fakes.fake_adapters as fake_adapters

LOGGER_NAME = "src.services.use_cases.conversation_control_service"


def build_service() -> tuple[
    conversation_control_service.ConversationControlService,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    service = conversation_control_service.ConversationControlService(
        conversation_repository=repository,
        scheduling_repository=scheduling_repository,
        clock=clock,
    )
    return service, repository, scheduling_repository


def build_claims(role: str, tenant_id: str = "tenant-1") -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id=tenant_id,
        role=role,
        exp=2_000_000_000,
        jti="jti-1",
        token_kind="access",
    )


def test_update_control_mode_switches_human_and_ai() -> None:
    service, repository, _ = build_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="hello",
            message_ids=[],
            control_mode="AI",
        )
    )
    owner_claims = build_claims(role="owner")

    human_result = service.update_control_mode(
        claims=owner_claims,
        conversation_id="conv-1",
        update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
    )
    ai_result = service.update_control_mode(
        claims=owner_claims,
        conversation_id="conv-1",
        update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="AI"),
    )

    assert human_result.control_mode == "HUMAN"
    assert ai_result.control_mode == "AI"


def test_update_control_mode_rejects_non_owner() -> None:
    service, repository, _ = build_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="hello",
            message_ids=[],
            control_mode="AI",
        )
    )

    with pytest.raises(service_exceptions.AuthorizationError):
        service.update_control_mode(
            claims=build_claims(role="agent"),
            conversation_id="conv-1",
            update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
        )


def test_reset_messages_clears_active_messages_without_creating_subsession() -> None:
    service, repository, scheduling_repository = build_service()
    started_at = datetime.datetime(2025, 12, 31, tzinfo=datetime.UTC)
    message_created_at = datetime.datetime(2025, 12, 31, 12, tzinfo=datetime.UTC)
    archived_at = datetime.datetime(2025, 12, 30, tzinfo=datetime.UTC)
    active_message = message_entity.Message(
        id="msg-active-1",
        conversation_id="conv-1",
        tenant_id="tenant-1",
        direction="INBOUND",
        role="user",
        content="Hola",
        provider_message_id=None,
        created_at=message_created_at,
    )
    archived_message = message_entity.Message(
        id="msg-archived-1",
        conversation_id="conv-1",
        tenant_id="tenant-1",
        direction="OUTBOUND",
        role="assistant",
        content="Cita confirmada",
        provider_message_id="wamid-archived-1",
        created_at=archived_at,
    )

    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=started_at,
            updated_at=started_at,
            last_message_preview="Hola",
            message_ids=["msg-active-1"],
            messages=[active_message],
            control_mode="HUMAN",
            subsessions=[
                conversation_entity.ConversationSubsession(
                    archived_at=archived_at,
                    archived_reason="APPOINTMENT_BOOKED",
                    scheduling_request_id="req-1",
                    calendar_event_id="evt-1",
                    messages=[archived_message],
                )
            ],
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-active-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=started_at,
            updated_at=started_at,
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-closed-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-1",
            request_kind="INITIAL",
            status="BOOKED",
            round_number=2,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id="evt-1",
            created_at=started_at,
            updated_at=started_at,
        )
    )

    service.reset_messages(
        claims=build_claims(role="owner"),
        conversation_id="conv-1",
    )

    conversation = repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert conversation.message_ids == []
    assert conversation.messages == []
    assert conversation.last_message_preview is None
    assert conversation.updated_at == datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    assert len(conversation.subsessions) == 1
    assert conversation.subsessions[0].messages[0].id == "msg-archived-1"
    assert repository.list_messages("tenant-1", "conv-1") == []
    active_request = scheduling_repository.get_request_by_id("tenant-1", "req-active-1")
    booked_request = scheduling_repository.get_request_by_id("tenant-1", "req-closed-1")
    assert active_request is not None
    assert booked_request is not None
    assert active_request.status == "CANCELLED"
    assert active_request.professional_note == "conversation reset by owner"
    assert active_request.updated_at == datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    assert booked_request.status == "BOOKED"


def test_reset_messages_cancels_awaiting_payment_confirmation_requests() -> None:
    started_at = datetime.datetime(2025, 12, 31, tzinfo=datetime.UTC)
    service_repo, repository, scheduling_repository = build_service()
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=started_at,
            updated_at=started_at,
            last_message_preview="Hola",
            message_ids=[],
            control_mode="AI",
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-payment-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-1",
            request_kind="INITIAL",
            status="AWAITING_PAYMENT_CONFIRMATION",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=started_at,
            updated_at=started_at,
        )
    )

    service_repo.reset_messages(
        claims=build_claims(role="owner"),
        conversation_id="conv-1",
    )

    payment_request = scheduling_repository.get_request_by_id("tenant-1", "req-payment-1")
    assert payment_request is not None
    assert payment_request.status == "CANCELLED"
    assert payment_request.professional_note == "conversation reset by owner"


def test_reset_messages_rejects_non_owner() -> None:
    service, repository, _ = build_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="hello",
            message_ids=["msg-1"],
            control_mode="AI",
        )
    )

    with pytest.raises(service_exceptions.AuthorizationError):
        service.reset_messages(
            claims=build_claims(role="agent"),
            conversation_id="conv-1",
        )


def test_update_control_mode_fails_when_conversation_not_found_or_other_tenant() -> None:
    service, repository, _ = build_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-2",
            tenant_id="tenant-2",
            whatsapp_user_id="wa-2",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="hello",
            message_ids=[],
            control_mode="AI",
        )
    )

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.update_control_mode(
            claims=build_claims(role="owner", tenant_id="tenant-1"),
            conversation_id="conv-2",
            update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
        )


def test_reset_messages_fails_when_conversation_not_found_or_other_tenant() -> None:
    service, repository, _ = build_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-2",
            tenant_id="tenant-2",
            whatsapp_user_id="wa-2",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="hello",
            message_ids=["msg-1"],
            control_mode="AI",
        )
    )

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.reset_messages(
            claims=build_claims(role="owner", tenant_id="tenant-1"),
            conversation_id="conv-2",
        )


def test_update_control_mode_logs_control_mode_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, repository, _ = build_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="hello",
            message_ids=[],
            control_mode="AI",
        )
    )
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    service.update_control_mode(
        claims=build_claims(role="owner"),
        conversation_id="conv-1",
        update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
    )

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "conversation.control_mode_changed" in events
