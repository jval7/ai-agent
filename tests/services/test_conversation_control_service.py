import datetime
import logging

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
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
    patient_repository_adapter.InMemoryPatientRepositoryAdapter,
    fake_adapters.FakeWhatsappProvider,
    whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    patient_repo = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    whatsapp_connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-1", "msg-2", "msg-3"])
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    service = conversation_control_service.ConversationControlService(
        conversation_repository=repository,
        scheduling_repository=scheduling_repository,
        patient_repository=patient_repo,
        whatsapp_connection_repository=whatsapp_connection_repository,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
    )
    return (
        service,
        repository,
        scheduling_repository,
        patient_repo,
        whatsapp_provider,
        whatsapp_connection_repository,
    )


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
    service, repository, _, _, _, _ = build_service()
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
    professional_claims = build_claims(role="professional")

    human_result = service.update_control_mode(
        claims=professional_claims,
        conversation_id="conv-1",
        update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
    )
    ai_result = service.update_control_mode(
        claims=professional_claims,
        conversation_id="conv-1",
        update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="AI"),
    )

    assert human_result.control_mode == "HUMAN"
    assert ai_result.control_mode == "AI"


def test_update_control_mode_rejects_non_professional() -> None:
    service, repository, _, _, _, _ = build_service()
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


def test_reset_deletes_conversation_user_patient_and_scheduling_requests() -> None:
    service, repository, scheduling_repository, patient_repo, _, _ = build_service()
    started_at = datetime.datetime(2025, 12, 31, tzinfo=datetime.UTC)

    repository.save_whatsapp_user(
        whatsapp_user_entity.WhatsappUser(
            id="wa-1",
            tenant_id="tenant-1",
            display_name="Maria Lopez",
            created_at=started_at,
        )
    )
    patient_repo.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Maria",
            last_name="Lopez",
            email="maria@test.com",
            age=30,
            location="Bogota",
            phone="573001110001",
            created_at=started_at,
        )
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
            control_mode="AI",
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
            id="req-booked-1",
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
        claims=build_claims(role="professional"),
        conversation_id="conv-1",
    )

    assert repository.get_conversation_by_id("tenant-1", "conv-1") is None
    assert repository.get_whatsapp_user("tenant-1", "wa-1") is None
    assert patient_repo.get_by_whatsapp_user("tenant-1", "wa-1") is None
    assert scheduling_repository.get_request_by_id("tenant-1", "req-active-1") is None
    assert scheduling_repository.get_request_by_id("tenant-1", "req-booked-1") is None


def test_reset_messages_rejects_non_professional() -> None:
    service, repository, _, _, _, _ = build_service()
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
    service, repository, _, _, _, _ = build_service()
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
            claims=build_claims(role="professional", tenant_id="tenant-1"),
            conversation_id="conv-2",
            update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
        )


def test_reset_messages_fails_when_conversation_not_found_or_other_tenant() -> None:
    service, repository, _, _, _, _ = build_service()
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
            claims=build_claims(role="professional", tenant_id="tenant-1"),
            conversation_id="conv-2",
        )


def test_update_control_mode_logs_control_mode_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, repository, _, _, _, _ = build_service()
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
        claims=build_claims(role="professional"),
        conversation_id="conv-1",
        update_dto=conversation_dto.UpdateConversationControlModeDTO(control_mode="HUMAN"),
    )

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "conversation.control_mode_changed" in events


# ---------------------------------------------------------------------------
# send_professional_message
# ---------------------------------------------------------------------------


def _seed_human_conversation(
    repository: conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    *,
    control_mode: str = "HUMAN",
) -> None:
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode=control_mode,  # type: ignore[arg-type]
        )
    )


def _seed_connection(
    connection_repository: whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
    *,
    access_token: str | None,
    phone_number_id: str | None,
) -> None:
    connection_repository.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id=phone_number_id,
            business_account_id="business-1",
            access_token=access_token,
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )


def test_send_professional_message_persists_outbound_and_returns_response() -> None:
    service, repository, _, _, whatsapp_provider, connection_repo = build_service()
    _seed_human_conversation(repository, control_mode="HUMAN")
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")

    response = service.send_professional_message(
        claims=build_claims(role="professional"),
        conversation_id="conv-1",
        send_dto=conversation_dto.SendProfessionalMessageDTO(message_text="Hola, ¿cómo estás?"),
    )

    assert response.role == "human_agent"
    assert response.content == "Hola, ¿cómo estás?"
    assert response.conversation_id == "conv-1"
    assert len(whatsapp_provider.sent_messages) == 1
    assert whatsapp_provider.sent_messages[0]["whatsapp_user_id"] == "wa-user-1"
    assert whatsapp_provider.sent_messages[0]["text"] == "Hola, ¿cómo estás?"
    persisted = repository.list_messages("tenant-1", "conv-1")
    assert len(persisted) == 1
    assert persisted[0].role == "human_agent"
    assert persisted[0].direction == "OUTBOUND"


def test_send_professional_message_rejects_non_professional() -> None:
    service, repository, _, _, whatsapp_provider, connection_repo = build_service()
    _seed_human_conversation(repository, control_mode="HUMAN")
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")

    with pytest.raises(service_exceptions.AuthorizationError):
        service.send_professional_message(
            claims=build_claims(role="member"),
            conversation_id="conv-1",
            send_dto=conversation_dto.SendProfessionalMessageDTO(message_text="hola"),
        )

    assert whatsapp_provider.sent_messages == []


def test_send_professional_message_raises_when_conversation_missing() -> None:
    service, _, _, _, _, connection_repo = build_service()
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.send_professional_message(
            claims=build_claims(role="professional"),
            conversation_id="conv-missing",
            send_dto=conversation_dto.SendProfessionalMessageDTO(message_text="hola"),
        )


def test_send_professional_message_requires_human_mode() -> None:
    service, repository, _, _, whatsapp_provider, connection_repo = build_service()
    _seed_human_conversation(repository, control_mode="AI")
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.send_professional_message(
            claims=build_claims(role="professional"),
            conversation_id="conv-1",
            send_dto=conversation_dto.SendProfessionalMessageDTO(message_text="hola"),
        )

    assert whatsapp_provider.sent_messages == []


def test_send_professional_message_raises_when_connection_missing_credentials() -> None:
    service, repository, _, _, whatsapp_provider, connection_repo = build_service()
    _seed_human_conversation(repository, control_mode="HUMAN")
    _seed_connection(connection_repo, access_token=None, phone_number_id="phone-1")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.send_professional_message(
            claims=build_claims(role="professional"),
            conversation_id="conv-1",
            send_dto=conversation_dto.SendProfessionalMessageDTO(message_text="hola"),
        )

    assert whatsapp_provider.sent_messages == []
