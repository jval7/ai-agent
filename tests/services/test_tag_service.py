import datetime

import pytest

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tag_repository_adapter as tag_repository_adapter
import src.domain.entities.conversation as conversation_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.tag_dto as tag_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.tag_service as tag_service_module
import tests.fakes.fake_adapters as fake_adapters


def build_tag_service() -> tuple[
    tag_service_module.TagService,
    tag_repository_adapter.InMemoryTagRepositoryAdapter,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    fake_adapters.FixedClock,
]:
    store = in_memory_store.InMemoryStore()
    tag_repository = tag_repository_adapter.InMemoryTagRepositoryAdapter(store)
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_values = [f"tag-{index}" for index in range(1, 30)]
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    service = tag_service_module.TagService(
        tag_repository=tag_repository,
        conversation_repository=conversation_repository,
        id_generator=id_generator,
        clock=clock,
    )
    return service, tag_repository, conversation_repository, clock


def build_claims(
    role: str = "professional", tenant_id: str = "tenant-1"
) -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id=tenant_id,
        role=role,
        exp=2_000_000_000,
        jti="jti-1",
        token_kind="access",
    )


def _save_conversation(
    repository: conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    conversation_id: str,
    tenant_id: str,
    now_value: datetime.datetime,
) -> None:
    repository.save_conversation(
        conversation_entity.Conversation(
            id=conversation_id,
            tenant_id=tenant_id,
            whatsapp_user_id=f"wa-{conversation_id}",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
        )
    )


def test_ensure_system_tags_creates_all_expected_slugs() -> None:
    service, tag_repository, _, _ = build_tag_service()

    tags_by_slug = service.ensure_system_tags("tenant-1")

    expected_slugs = {
        definition["slug"] for definition in tag_service_module.SYSTEM_TAG_DEFINITIONS
    }
    assert set(tags_by_slug.keys()) == expected_slugs
    persisted = tag_repository.list_by_tenant("tenant-1")
    assert {tag.slug for tag in persisted} == expected_slugs
    for tag in persisted:
        assert tag.tag_type == "SYSTEM"


def test_ensure_system_tags_is_idempotent() -> None:
    service, tag_repository, _, _ = build_tag_service()

    first_call = service.ensure_system_tags("tenant-1")
    second_call = service.ensure_system_tags("tenant-1")

    assert {tag.id for tag in first_call.values()} == {tag.id for tag in second_call.values()}
    persisted = tag_repository.list_by_tenant("tenant-1")
    assert len(persisted) == len(tag_service_module.SYSTEM_TAG_DEFINITIONS)


def test_create_custom_tag_persists_custom_slug() -> None:
    service, tag_repository, _, _ = build_tag_service()
    claims = build_claims()

    created = service.create_custom_tag(
        claims,
        tag_dto.CreateTagDTO(name="VIP Patient", color="#FF0000"),
    )

    assert created.tag_type == "CUSTOM"
    assert created.slug == "custom-vip-patient"
    assert created.color == "#FF0000"
    persisted = tag_repository.list_by_tenant("tenant-1")
    assert any(item.slug == "custom-vip-patient" for item in persisted)


def test_create_custom_tag_rejects_duplicate_slug() -> None:
    service, _, _, _ = build_tag_service()
    claims = build_claims()

    service.create_custom_tag(
        claims,
        tag_dto.CreateTagDTO(name="VIP", color="#FF0000"),
    )

    with pytest.raises(service_exceptions.InvalidStateError):
        service.create_custom_tag(
            claims,
            tag_dto.CreateTagDTO(name="vip", color="#00FF00"),
        )


def test_update_custom_tag_allows_name_and_color_change() -> None:
    service, _, _, _ = build_tag_service()
    claims = build_claims()

    created = service.create_custom_tag(
        claims,
        tag_dto.CreateTagDTO(name="VIP", color="#FF0000"),
    )

    updated = service.update_tag(
        claims,
        created.id,
        tag_dto.UpdateTagDTO(name="Premium Patient", color="#00FF00"),
    )

    assert updated.name == "Premium Patient"
    assert updated.color == "#00FF00"
    assert updated.slug == "custom-premium-patient"


def test_update_system_tag_rejects_name_change_but_allows_color() -> None:
    service, _, _, _ = build_tag_service()
    claims = build_claims()
    system_tags = service.ensure_system_tags("tenant-1")
    booked_tag = system_tags["booked"]

    with pytest.raises(service_exceptions.InvalidStateError):
        service.update_tag(
            claims,
            booked_tag.id,
            tag_dto.UpdateTagDTO(name="Agendada custom", color="#123456"),
        )

    updated = service.update_tag(
        claims,
        booked_tag.id,
        tag_dto.UpdateTagDTO(name=None, color="#123456"),
    )
    assert updated.color == "#123456"
    assert updated.tag_type == "SYSTEM"
    assert updated.slug == "booked"


def test_delete_tag_rejects_system_tag() -> None:
    service, _, _, _ = build_tag_service()
    claims = build_claims()
    system_tags = service.ensure_system_tags("tenant-1")
    booked_tag = system_tags["booked"]

    with pytest.raises(service_exceptions.InvalidStateError):
        service.delete_tag(claims, booked_tag.id)


def test_delete_custom_tag_removes_it_from_all_conversations() -> None:
    service, tag_repository, conversation_repository, clock = build_tag_service()
    claims = build_claims()
    _save_conversation(conversation_repository, "conv-1", "tenant-1", clock.now())

    created = service.create_custom_tag(
        claims,
        tag_dto.CreateTagDTO(name="Urgent", color="#FF0000"),
    )
    service.assign_tag_to_conversation(claims, "conv-1", created.id)

    conversation = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert created.id in conversation.tag_ids

    service.delete_tag(claims, created.id)

    assert tag_repository.get_by_id("tenant-1", created.id) is None
    conversation_after = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation_after is not None
    assert created.id not in conversation_after.tag_ids


def test_assign_and_remove_tag_to_conversation_with_system_tag() -> None:
    service, _, conversation_repository, clock = build_tag_service()
    claims = build_claims()
    _save_conversation(conversation_repository, "conv-1", "tenant-1", clock.now())
    system_tags = service.ensure_system_tags("tenant-1")
    booked_tag = system_tags["booked"]

    service.assign_tag_to_conversation(claims, "conv-1", booked_tag.id)
    conversation = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert booked_tag.id in conversation.tag_ids

    service.remove_tag_from_conversation(claims, "conv-1", booked_tag.id)
    conversation_after = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation_after is not None
    assert booked_tag.id not in conversation_after.tag_ids


def test_sync_scheduling_tags_replaces_previous_system_tag() -> None:
    service, _, conversation_repository, clock = build_tag_service()
    _save_conversation(conversation_repository, "conv-1", "tenant-1", clock.now())

    service.sync_scheduling_tags(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        new_status="AWAITING_CONSULTATION_REVIEW",
    )
    system_tags = service.ensure_system_tags("tenant-1")
    review_tag = system_tags["awaiting-consultation-review"]
    booked_tag = system_tags["booked"]

    conversation_after_first = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation_after_first is not None
    assert conversation_after_first.tag_ids == [review_tag.id]

    service.sync_scheduling_tags(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        new_status="BOOKED",
    )
    conversation_after_second = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation_after_second is not None
    assert conversation_after_second.tag_ids == [booked_tag.id]


def test_sync_scheduling_tags_preserves_custom_tags() -> None:
    service, _, conversation_repository, clock = build_tag_service()
    claims = build_claims()
    _save_conversation(conversation_repository, "conv-1", "tenant-1", clock.now())
    custom_tag = service.create_custom_tag(
        claims,
        tag_dto.CreateTagDTO(name="VIP", color="#FF0000"),
    )
    service.assign_tag_to_conversation(claims, "conv-1", custom_tag.id)

    service.sync_scheduling_tags(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        new_status="BOOKED",
    )

    conversation = conversation_repository.get_conversation_by_id("tenant-1", "conv-1")
    assert conversation is not None
    assert custom_tag.id in conversation.tag_ids


def test_sync_scheduling_tags_is_noop_when_conversation_missing() -> None:
    service, _, conversation_repository, _ = build_tag_service()

    service.sync_scheduling_tags(
        tenant_id="tenant-1",
        conversation_id="missing",
        new_status="BOOKED",
    )

    assert conversation_repository.get_conversation_by_id("tenant-1", "missing") is None


def test_list_tags_requires_professional_role() -> None:
    service, _, _, _ = build_tag_service()
    non_professional_claims = build_claims(role="agent")

    with pytest.raises(service_exceptions.AuthorizationError):
        service.list_tags(non_professional_claims)
