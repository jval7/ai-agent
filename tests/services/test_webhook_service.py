import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.processed_webhook_event_repository_adapter as processed_webhook_event_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.webhook_service as webhook_service
import tests.fakes.fake_adapters as fake_adapters


def build_webhook_service(
    id_values: list[str],
) -> tuple[
    webhook_service.WebhookService,
    fake_adapters.FakeWhatsappProvider,
    fake_adapters.FakeLlmProvider,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    processed_repository = (
        processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter(
            store
        )
    )
    agent_profile_repository = (
        agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    )

    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    connection_repository.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=now_value,
        )
    )
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="assistant reply")
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    clock = fake_adapters.FixedClock(now_value)

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        processed_webhook_event_repository=processed_repository,
        agent_profile_repository=agent_profile_repository,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
    )

    return service, provider, llm_provider, conversation_repository, processed_repository


def build_text_event() -> webhook_dto.IncomingMessageEventDTO:
    return webhook_dto.IncomingMessageEventDTO(
        provider_event_id="evt-1",
        phone_number_id="phone-1",
        whatsapp_user_id="wa-user-1",
        whatsapp_user_name="Jane",
        message_id="wamid-in-1",
        message_text="hello",
    )


def test_process_payload_creates_conversation_and_outbound_reply() -> None:
    service, provider, llm_provider, conversation_repository, processed_repository = (
        build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    )
    provider.events = [build_text_event()]

    result = service.process_payload({})

    assert result.status == "processed"
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0]["text"] == "assistant reply"
    assert len(llm_provider.calls) == 1
    assert llm_provider.calls[0].system_prompt == "tenant custom prompt"

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert processed_repository.exists("tenant-1", "evt-1")


def test_process_payload_dedupes_same_event() -> None:
    service, provider, _, conversation_repository, _ = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"]
    )
    provider.events = [build_text_event()]

    service.process_payload({})
    service.process_payload({})

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert len(provider.sent_messages) == 1


def test_process_payload_bubbles_llm_failures_without_marking_event_processed() -> None:
    service, provider, llm_provider, conversation_repository, processed_repository = (
        build_webhook_service(["conversation-1", "in-msg-1"])
    )
    provider.events = [build_text_event()]
    llm_provider.should_fail = True

    with pytest.raises(service_exceptions.ExternalProviderError):
        service.process_payload({})

    assert not processed_repository.exists("tenant-1", "evt-1")
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 1
    assert messages[0].direction == "INBOUND"
