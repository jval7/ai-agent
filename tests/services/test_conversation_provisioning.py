import datetime

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.services.use_cases.conversation_provisioning as conversation_provisioning
import tests.fakes.fake_adapters as fake_adapters

TENANT_ID = "tenant-1"
WHATSAPP_USER_ID = "wa-user-1"
NOW = datetime.datetime(2026, 5, 4, 10, 0, tzinfo=datetime.UTC)


def _build_repository() -> conversation_repository_adapter.InMemoryConversationRepositoryAdapter:
    store = in_memory_store.InMemoryStore()
    return conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)


def test_creates_user_and_conversation_when_neither_exists() -> None:
    repository = _build_repository()
    id_generator = fake_adapters.SequenceIdGenerator(["conv-new"])

    user, conversation = conversation_provisioning.ensure_conversation_for_whatsapp_user(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        display_name="Ana Lopez",
        now_value=NOW,
        conversation_repository=repository,
        id_generator=id_generator,
    )

    assert user.id == WHATSAPP_USER_ID
    assert user.tenant_id == TENANT_ID
    assert user.display_name == "Ana Lopez"
    assert user.created_at == NOW
    assert conversation.id == "conv-new"
    assert conversation.tenant_id == TENANT_ID
    assert conversation.whatsapp_user_id == WHATSAPP_USER_ID
    assert conversation.started_at == NOW
    assert conversation.updated_at == NOW
    assert conversation.last_message_preview is None
    assert conversation.message_ids == []
    assert conversation.control_mode == "AI"

    persisted_user = repository.get_whatsapp_user(TENANT_ID, WHATSAPP_USER_ID)
    persisted_conversation = repository.get_conversation_by_whatsapp_user(
        TENANT_ID, WHATSAPP_USER_ID
    )
    assert persisted_user is not None
    assert persisted_user.display_name == "Ana Lopez"
    assert persisted_conversation is not None
    assert persisted_conversation.id == "conv-new"


def test_creates_only_conversation_when_user_already_exists() -> None:
    repository = _build_repository()
    repository.save_whatsapp_user(
        whatsapp_user_entity.WhatsappUser(
            id=WHATSAPP_USER_ID,
            tenant_id=TENANT_ID,
            display_name="Existing User",
            created_at=NOW - datetime.timedelta(days=3),
        )
    )
    id_generator = fake_adapters.SequenceIdGenerator(["conv-new"])

    user, conversation = conversation_provisioning.ensure_conversation_for_whatsapp_user(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        display_name="Should Not Replace",
        now_value=NOW,
        conversation_repository=repository,
        id_generator=id_generator,
    )

    assert user.display_name == "Existing User"
    assert user.created_at == NOW - datetime.timedelta(days=3)
    assert conversation.id == "conv-new"
    assert conversation.started_at == NOW


def test_returns_existing_conversation_without_creating_new_one() -> None:
    repository = _build_repository()
    earlier = NOW - datetime.timedelta(days=1)
    repository.save_whatsapp_user(
        whatsapp_user_entity.WhatsappUser(
            id=WHATSAPP_USER_ID,
            tenant_id=TENANT_ID,
            display_name="Existing User",
            created_at=earlier,
        )
    )
    repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-existing",
            tenant_id=TENANT_ID,
            whatsapp_user_id=WHATSAPP_USER_ID,
            started_at=earlier,
            updated_at=earlier,
            last_message_preview="hola",
            message_ids=["msg-existing"],
            control_mode="HUMAN",
        )
    )
    id_generator = fake_adapters.SequenceIdGenerator(["unused"])

    user, conversation = conversation_provisioning.ensure_conversation_for_whatsapp_user(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        display_name="Should Not Replace",
        now_value=NOW,
        conversation_repository=repository,
        id_generator=id_generator,
    )

    assert user.display_name == "Existing User"
    assert conversation.id == "conv-existing"
    assert conversation.started_at == earlier
    assert conversation.control_mode == "HUMAN"
    assert conversation.message_ids == ["msg-existing"]


def test_accepts_none_display_name_for_new_user() -> None:
    repository = _build_repository()
    id_generator = fake_adapters.SequenceIdGenerator(["conv-new"])

    user, _ = conversation_provisioning.ensure_conversation_for_whatsapp_user(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        display_name=None,
        now_value=NOW,
        conversation_repository=repository,
        id_generator=id_generator,
    )

    assert user.display_name is None
