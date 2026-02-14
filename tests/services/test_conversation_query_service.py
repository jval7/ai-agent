import datetime

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.services.exceptions as service_exceptions
import src.services.use_cases.conversation_query_service as conversation_query_service


def build_query_service() -> tuple[
    conversation_query_service.ConversationQueryService,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    service = conversation_query_service.ConversationQueryService(
        conversation_repository=repository
    )
    return service, repository


def test_list_conversations_returns_only_tenant_data() -> None:
    service, repository = build_query_service()
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
        )
    )
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-2",
            tenant_id="tenant-2",
            whatsapp_user_id="wa-2",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="private",
            message_ids=[],
        )
    )

    result = service.list_conversations("tenant-1")

    assert len(result.items) == 1
    assert result.items[0].conversation_id == "conv-1"


def test_list_messages_raises_when_conversation_not_found_for_tenant() -> None:
    service, repository = build_query_service()
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-2",
            tenant_id="tenant-2",
            whatsapp_user_id="wa-2",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview="private",
            message_ids=[],
        )
    )

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.list_messages("tenant-1", "conv-2")


def test_list_messages_returns_ordered_history() -> None:
    service, repository = build_query_service()
    base_time = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            started_at=base_time,
            updated_at=base_time,
            last_message_preview="hello",
            message_ids=[],
        )
    )

    repository.save_message(
        message_entity.Message(
            id="msg-2",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            direction="OUTBOUND",
            role="assistant",
            content="second",
            provider_message_id="p2",
            created_at=base_time + datetime.timedelta(seconds=2),
        )
    )
    repository.save_message(
        message_entity.Message(
            id="msg-1",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            direction="INBOUND",
            role="user",
            content="first",
            provider_message_id="p1",
            created_at=base_time + datetime.timedelta(seconds=1),
        )
    )

    response = service.list_messages("tenant-1", "conv-1")

    assert len(response.items) == 2
    assert response.items[0].message_id == "msg-1"
    assert response.items[1].message_id == "msg-2"
