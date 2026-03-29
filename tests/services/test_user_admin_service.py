import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.domain.entities.tenant as tenant_entity
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
    password_hasher_adapter.Pbkdf2PasswordHasherAdapter,
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
    return service, tenant_repository, user_repository, agent_profile_repository, password_hasher


def test_bootstrap_master_creates_tenant_master_user_and_default_prompt() -> None:
    service, tenant_repository, user_repository, agent_profile_repository, _ = (
        build_user_admin_service(["tenant-1", "user-1"])
    )

    service.bootstrap_master(
        user_admin_dto.BootstrapMasterDTO(
            tenant_name="Acme",
            master_email="master@acme.com",
            master_password="supersecret",
        )
    )

    tenant = tenant_repository.get_by_id("tenant-1")
    user = user_repository.get_by_email("master@acme.com")
    agent_profile = agent_profile_repository.get_by_tenant_id("tenant-1")

    assert tenant is not None
    assert user is not None
    assert agent_profile is not None
    assert user.is_master is True
    assert user.role == "professional"


def test_bootstrap_master_promotes_existing_user_when_credentials_are_valid() -> None:
    service, tenant_repository, user_repository, agent_profile_repository, password_hasher = (
        build_user_admin_service([])
    )
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    tenant_repository.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Acme",
            created_at=now_value,
            updated_at=now_value,
        )
    )
    user_repository.save(
        user_entity.User(
            id="user-1",
            tenant_id="tenant-1",
            email="master@acme.com",
            password_hash=password_hasher.hash_password("supersecret"),
            role="professional",
            is_active=True,
            is_master=False,
            created_at=now_value,
        )
    )

    service.bootstrap_master(
        user_admin_dto.BootstrapMasterDTO(
            tenant_name="Ignored",
            master_email="master@acme.com",
            master_password="supersecret",
        )
    )

    promoted_user = user_repository.get_by_email("master@acme.com")
    agent_profile = agent_profile_repository.get_by_tenant_id("tenant-1")
    assert promoted_user is not None
    assert promoted_user.is_master is True
    assert agent_profile is not None


def test_create_user_creates_professional_user_in_same_tenant() -> None:
    service, _, user_repository, _, _ = build_user_admin_service(
        ["tenant-1", "user-master", "user-2"]
    )
    service.bootstrap_master(
        user_admin_dto.BootstrapMasterDTO(
            tenant_name="Acme",
            master_email="master@acme.com",
            master_password="supersecret",
        )
    )

    service.create_user(
        user_admin_dto.CreateUserDTO(
            tenant_email="master@acme.com",
            email="professional2@acme.com",
            password="supersecret2",
        )
    )

    created_user = user_repository.get_by_email("professional2@acme.com")
    assert created_user is not None
    assert created_user.role == "professional"
    assert created_user.is_master is False


def test_create_user_fails_when_tenant_email_not_found() -> None:
    service, _, _, _, _ = build_user_admin_service([])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.create_user(
            user_admin_dto.CreateUserDTO(
                tenant_email="nonexistent@acme.com",
                email="other@acme.com",
                password="supersecret2",
            )
        )


def test_delete_user_hard_deletes_regular_user_and_blocks_master_delete() -> None:
    service, _, user_repository, _, _ = build_user_admin_service(
        ["tenant-1", "user-master", "user-2"]
    )
    service.bootstrap_master(
        user_admin_dto.BootstrapMasterDTO(
            tenant_name="Acme",
            master_email="master@acme.com",
            master_password="supersecret",
        )
    )
    service.create_user(
        user_admin_dto.CreateUserDTO(
            tenant_email="master@acme.com",
            email="professional2@acme.com",
            password="supersecret2",
        )
    )
    created_user = user_repository.get_by_email("professional2@acme.com")
    assert created_user is not None

    service.delete_user(
        user_admin_dto.DeleteUserDTO(email="professional2@acme.com")
    )
    assert user_repository.get_by_email("professional2@acme.com") is None
    assert user_repository.get_by_id(created_user.id) is None

    with pytest.raises(service_exceptions.InvalidStateError):
        service.delete_user(
            user_admin_dto.DeleteUserDTO(email="master@acme.com")
        )


def test_delete_tenant_removes_tenant_users_and_all_data() -> None:
    service, tenant_repository, user_repository, agent_profile_repository, _ = (
        build_user_admin_service(["tenant-1", "user-master", "user-2"])
    )
    service.bootstrap_master(
        user_admin_dto.BootstrapMasterDTO(
            tenant_name="Acme",
            master_email="master@acme.com",
            master_password="supersecret",
        )
    )
    service.create_user(
        user_admin_dto.CreateUserDTO(
            tenant_email="master@acme.com",
            email="professional2@acme.com",
            password="supersecret2",
        )
    )

    assert tenant_repository.get_by_id("tenant-1") is not None
    assert user_repository.get_by_email("master@acme.com") is not None
    assert user_repository.get_by_email("professional2@acme.com") is not None
    assert agent_profile_repository.get_by_tenant_id("tenant-1") is not None

    service.delete_tenant(
        user_admin_dto.DeleteTenantDTO(email="master@acme.com")
    )

    assert tenant_repository.get_by_id("tenant-1") is None
    assert user_repository.get_by_email("master@acme.com") is None
    assert user_repository.get_by_email("professional2@acme.com") is None
    assert agent_profile_repository.get_by_tenant_id("tenant-1") is None


def test_delete_tenant_fails_when_user_not_found() -> None:
    service, _, _, _, _ = build_user_admin_service([])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.delete_tenant(
            user_admin_dto.DeleteTenantDTO(email="nonexistent@acme.com")
        )
