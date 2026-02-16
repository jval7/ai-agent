import datetime
import logging

import pytest

import src.adapters.outbound.inmemory.blacklist_repository_adapter as blacklist_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.services.dto.auth_dto as auth_dto
import src.services.dto.blacklist_dto as blacklist_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.blacklist_service as blacklist_service
import tests.fakes.fake_adapters as fake_adapters

LOGGER_NAME = "src.services.use_cases.blacklist_service"


def build_blacklist_service() -> blacklist_service.BlacklistService:
    store = in_memory_store.InMemoryStore()
    repository = blacklist_repository_adapter.InMemoryBlacklistRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    return blacklist_service.BlacklistService(
        blacklist_repository=repository,
        clock=clock,
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


def test_blacklist_add_list_delete_is_isolated_per_tenant() -> None:
    service = build_blacklist_service()
    owner_tenant_1 = build_claims(role="owner", tenant_id="tenant-1")
    owner_tenant_2 = build_claims(role="owner", tenant_id="tenant-2")

    service.upsert_entry(
        owner_tenant_1,
        blacklist_dto.UpsertBlacklistEntryDTO(whatsapp_user_id="wa-user-1"),
    )
    service.upsert_entry(
        owner_tenant_2,
        blacklist_dto.UpsertBlacklistEntryDTO(whatsapp_user_id="wa-user-2"),
    )

    tenant_1_entries = service.list_entries(owner_tenant_1)
    tenant_2_entries = service.list_entries(owner_tenant_2)

    assert len(tenant_1_entries.items) == 1
    assert tenant_1_entries.items[0].whatsapp_user_id == "wa-user-1"
    assert len(tenant_2_entries.items) == 1
    assert tenant_2_entries.items[0].whatsapp_user_id == "wa-user-2"

    service.delete_entry(owner_tenant_1, "wa-user-1")
    tenant_1_after_delete = service.list_entries(owner_tenant_1)
    assert tenant_1_after_delete.items == []
    assert len(service.list_entries(owner_tenant_2).items) == 1


def test_blacklist_upsert_is_idempotent_for_same_contact() -> None:
    service = build_blacklist_service()
    owner_claims = build_claims(role="owner")

    first_entry = service.upsert_entry(
        owner_claims,
        blacklist_dto.UpsertBlacklistEntryDTO(whatsapp_user_id="wa-user-1"),
    )
    second_entry = service.upsert_entry(
        owner_claims,
        blacklist_dto.UpsertBlacklistEntryDTO(whatsapp_user_id="wa-user-1"),
    )

    entries = service.list_entries(owner_claims)
    assert len(entries.items) == 1
    assert first_entry.created_at == second_entry.created_at


def test_blacklist_requires_owner_role() -> None:
    service = build_blacklist_service()
    non_owner_claims = build_claims(role="agent")

    with pytest.raises(service_exceptions.AuthorizationError):
        service.list_entries(non_owner_claims)

    with pytest.raises(service_exceptions.AuthorizationError):
        service.upsert_entry(
            non_owner_claims,
            blacklist_dto.UpsertBlacklistEntryDTO(whatsapp_user_id="wa-user-1"),
        )

    with pytest.raises(service_exceptions.AuthorizationError):
        service.delete_entry(non_owner_claims, "wa-user-1")


def test_blacklist_logs_add_and_delete_events(caplog: pytest.LogCaptureFixture) -> None:
    service = build_blacklist_service()
    owner_claims = build_claims(role="owner")
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    service.upsert_entry(
        owner_claims,
        blacklist_dto.UpsertBlacklistEntryDTO(whatsapp_user_id="wa-user-1"),
    )
    service.delete_entry(owner_claims, "wa-user-1")

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "blacklist.entry_added" in events
    assert "blacklist.entry_deleted" in events
