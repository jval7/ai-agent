import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.domain.entities.user as user_entity
import src.services.dto.user_admin_dto as user_admin_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.user_admin_service as user_admin_service
import tests.fakes.fake_adapters as fake_adapters


def build_user_admin_service(
    id_values: list[str],
) -> tuple[
    user_admin_service.UserAdminService,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    user_repository_adapter.InMemoryUserRepositoryAdapter,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    tenant_repository = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repository = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repository = (
        agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    )
    password_hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)

    service = user_admin_service.UserAdminService(
        tenant_repository=tenant_repository,
        user_repository=user_repository,
        agent_profile_repository=agent_profile_repository,
        password_hasher=password_hasher,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default-prompt",
    )
    return service, tenant_repository, user_repository, agent_profile_repository


def test_create_professional_creates_tenant_user_and_agent_profile() -> None:
    service, tenant_repository, user_repository, agent_profile_repository = (
        build_user_admin_service(["tenant-1", "user-1"])
    )

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Acme",
            email="doc@acme.com",
            password="supersecret",
        )
    )

    tenant = tenant_repository.get_by_id("tenant-1")
    user = user_repository.get_by_email("doc@acme.com")
    agent_profile = agent_profile_repository.get_by_tenant_id("tenant-1")

    assert tenant is not None
    assert tenant.name == "Acme"
    assert user is not None
    assert user.role == "professional"
    assert agent_profile is not None


def test_create_professional_fails_when_email_already_exists() -> None:
    service, _, _, _ = build_user_admin_service(["tenant-1", "user-1"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Acme",
            email="doc@acme.com",
            password="supersecret",
        )
    )

    with pytest.raises(service_exceptions.InvalidStateError):
        service.create_professional(
            user_admin_dto.CreateProfessionalDTO(
                tenant_name="Acme2",
                email="doc@acme.com",
                password="supersecret2",
            )
        )


def test_delete_professional_removes_tenant_and_user() -> None:
    service, tenant_repository, user_repository, agent_profile_repository = (
        build_user_admin_service(["tenant-1", "user-1"])
    )

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Acme",
            email="doc@acme.com",
            password="supersecret",
        )
    )

    assert tenant_repository.get_by_id("tenant-1") is not None
    assert user_repository.get_by_email("doc@acme.com") is not None
    assert agent_profile_repository.get_by_tenant_id("tenant-1") is not None

    service.delete_professional(user_admin_dto.DeleteProfessionalDTO(email="doc@acme.com"))

    assert tenant_repository.get_by_id("tenant-1") is None
    assert user_repository.get_by_email("doc@acme.com") is None
    assert agent_profile_repository.get_by_tenant_id("tenant-1") is None


def test_reset_password_updates_password_hash() -> None:
    service, _, user_repository, _ = build_user_admin_service(["tenant-1", "user-1"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Acme",
            email="doc@acme.com",
            password="supersecret",
        )
    )

    user_before = user_repository.get_by_email("doc@acme.com")
    assert user_before is not None
    old_hash = user_before.password_hash

    service.reset_password(
        user_admin_dto.ResetPasswordDTO(
            email="doc@acme.com",
            new_password="newsecretpass",
        )
    )

    user_after = user_repository.get_by_email("doc@acme.com")
    assert user_after is not None
    assert user_after.password_hash != old_hash


def test_reset_password_fails_when_user_not_found() -> None:
    service, _, _, _ = build_user_admin_service([])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.reset_password(
            user_admin_dto.ResetPasswordDTO(
                email="nonexistent@acme.com",
                new_password="newsecretpass",
            )
        )


def test_delete_professional_fails_when_user_not_found() -> None:
    service, _, _, _ = build_user_admin_service([])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.delete_professional(
            user_admin_dto.DeleteProfessionalDTO(email="nonexistent@acme.com")
        )


def test_list_professionals_returns_empty_when_no_users() -> None:
    service, _, _, _ = build_user_admin_service([])

    summaries = service.list_professionals()

    assert summaries == []


def test_list_professionals_returns_all_professionals_sorted_by_email() -> None:
    service, _, _, _ = build_user_admin_service(["tenant-b", "user-b", "tenant-a", "user-a"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Bravo Clinic",
            email="bravo@acme.com",
            password="supersecret",
        )
    )
    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Alpha Clinic",
            email="alpha@acme.com",
            password="supersecret",
        )
    )

    summaries = service.list_professionals()

    assert [summary.email for summary in summaries] == ["alpha@acme.com", "bravo@acme.com"]
    alpha_summary = summaries[0]
    assert alpha_summary.tenant_id == "tenant-a"
    assert alpha_summary.tenant_name == "Alpha Clinic"
    assert alpha_summary.user_id == "user-a"
    assert alpha_summary.role == "professional"
    assert alpha_summary.is_active is True
    bravo_summary = summaries[1]
    assert bravo_summary.tenant_id == "tenant-b"
    assert bravo_summary.tenant_name == "Bravo Clinic"
    assert bravo_summary.user_id == "user-b"


def test_list_professionals_uses_empty_tenant_name_when_tenant_missing() -> None:
    service, _, user_repository, _ = build_user_admin_service([])

    orphan_user = user_entity.User(
        id="user-orphan",
        tenant_id="tenant-missing",
        email="orphan@acme.com",
        password_hash="hash",
        role="professional",
        is_active=True,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    user_repository.save(orphan_user)

    summaries = service.list_professionals()

    assert len(summaries) == 1
    assert summaries[0].email == "orphan@acme.com"
    assert summaries[0].tenant_id == "tenant-missing"
    assert summaries[0].tenant_name == ""
