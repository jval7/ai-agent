import datetime

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.conversation_dto as conversation_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.conversation_control_service as conversation_control_service
import tests.fakes.fake_adapters as fake_adapters


def build_service() -> tuple[
    conversation_control_service.ConversationControlService,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    service = conversation_control_service.ConversationControlService(
        conversation_repository=repository,
        clock=clock,
    )
    return service, repository


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
    service, repository = build_service()
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
    service, repository = build_service()
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


def test_update_control_mode_fails_when_conversation_not_found_or_other_tenant() -> None:
    service, repository = build_service()
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
