import datetime

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.agentic.conversation_message_sender as conversation_message_sender_mod
import src.services.exceptions as service_exceptions
import tests.fakes.fake_adapters as fake_adapters

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_sender() -> tuple[
    conversation_message_sender_mod.ConversationMessageSender,
    fake_adapters.FakeWhatsappProvider,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["out-msg-1", "out-msg-2", "out-msg-3"])
    clock = fake_adapters.FixedClock(NOW)
    sender = conversation_message_sender_mod.ConversationMessageSender(
        whatsapp_provider=provider,
        conversation_repository=conversation_repo,
        id_generator=id_generator,
        clock=clock,
    )
    return sender, provider, conversation_repo


def _make_connection(
    access_token: str | None = "test-token",  # noqa: S107
) -> whatsapp_connection_entity.WhatsappConnection:
    return whatsapp_connection_entity.WhatsappConnection(
        tenant_id="tenant-1",
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token=access_token,
        status="CONNECTED",
        embedded_signup_state=None,
        updated_at=NOW,
    )


def test_send_assistant_message_persists_and_returns_provider_id() -> None:
    sender, provider, conversation_repo = _build_sender()
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=NOW,
            updated_at=NOW,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )

    provider_msg_id = sender.send_assistant_message(
        connection=_make_connection(),
        conversation_id="conv-1",
        tenant_id="tenant-1",
        whatsapp_user_id="wa-user-1",
        text="Hello from assistant",
    )

    assert provider_msg_id == "outbound-1"
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0]["text"] == "Hello from assistant"
    messages = conversation_repo.list_messages("tenant-1", "conv-1")
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert messages[0].content == "Hello from assistant"
    assert messages[0].direction == "OUTBOUND"
    conversation = conversation_repo.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert len(conversation.message_ids) == 1


def test_send_assistant_message_raises_when_missing_credentials() -> None:
    sender, _, _ = _build_sender()

    with pytest.raises(service_exceptions.InvalidStateError, match="missing credentials"):
        sender.send_assistant_message(
            connection=_make_connection(access_token=None),
            conversation_id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            text="should fail",
        )


def test_archive_messages_noop_when_no_new_subsession() -> None:
    sender, _, conversation_repo = _build_sender()
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=NOW,
            updated_at=NOW,
            last_message_preview=None,
            message_ids=["msg-1"],
            control_mode="AI",
        )
    )
    conversation_repo.save_message(
        message_entity.Message(
            id="msg-1",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            direction="INBOUND",
            role="user",
            content="hello",
            provider_message_id="wamid-1",
            created_at=NOW,
        )
    )

    sender.archive_messages_into_subsession_if_booking_occurred(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        subsessions_count_before_ai_reply=0,
    )

    messages = conversation_repo.list_messages("tenant-1", "conv-1")
    assert len(messages) == 1


def test_archive_messages_archives_when_new_subsession_added() -> None:
    sender, _, conversation_repo = _build_sender()
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=NOW,
            updated_at=NOW,
            last_message_preview="hello",
            message_ids=["msg-1"],
            control_mode="AI",
            subsessions=[
                conversation_entity.ConversationSubsession(
                    scheduling_request_id="req-1",
                    calendar_event_id="cal-evt-1",
                    messages=[],
                    archived_at=NOW,
                    archived_reason="APPOINTMENT_BOOKED",
                )
            ],
        )
    )
    conversation_repo.save_message(
        message_entity.Message(
            id="msg-1",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            direction="INBOUND",
            role="user",
            content="hello",
            provider_message_id="wamid-1",
            created_at=NOW,
        )
    )

    sender.archive_messages_into_subsession_if_booking_occurred(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        subsessions_count_before_ai_reply=0,
    )

    messages = conversation_repo.list_messages("tenant-1", "conv-1")
    assert len(messages) == 0
    conversation = conversation_repo.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert len(conversation.subsessions) == 1
    assert len(conversation.subsessions[0].messages) == 1
    assert conversation.message_ids == []
    assert conversation.last_message_preview is None
