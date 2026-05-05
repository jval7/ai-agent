import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.services.constants as service_constants
import src.services.dto.user_admin_dto as user_admin_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.user_admin_service as user_admin_service
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_service(
    id_values: list[str],
) -> tuple[
    user_admin_service.UserAdminService,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    user_repository_adapter.InMemoryUserRepositoryAdapter,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    clock = fake_adapters.FixedClock(_NOW)
    id_generator = fake_adapters.SequenceIdGenerator(id_values)

    service = user_admin_service.UserAdminService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=hasher,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default-prompt",
    )
    return service, tenant_repo, user_repo, agent_profile_repo


def test_create_admin_user_uses_admin_tenant_singleton() -> None:
    # For admin: sequence is [user_id, admin_tenant_id]
    service, tenant_repo, user_repo, _ = _build_service(["admin-user-id", "admin-tenant-id"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="ignored-for-admin",
            email="admin@example.com",
            password="secret123",
            role=service_constants.ROLE_ADMIN,
        )
    )

    user = user_repo.get_by_email("admin@example.com")
    assert user is not None
    assert user.role == service_constants.ROLE_ADMIN

    admin_tenant = tenant_repo.get_admin_tenant()
    assert admin_tenant is not None
    assert admin_tenant.is_admin_tenant is True
    assert user.tenant_id == admin_tenant.id


def test_create_admin_user_reuses_existing_admin_tenant() -> None:
    """Second admin user creation reuses the singleton admin tenant."""
    # Sequence: user1_id, admin_tenant_id (created on first call), user2_id (second call reuses tenant)
    service, tenant_repo, _, _ = _build_service(["user-1", "admin-tenant-id", "user-2"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="ignored",
            email="admin1@example.com",
            password="secret123",
            role=service_constants.ROLE_ADMIN,
        )
    )
    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="ignored",
            email="admin2@example.com",
            password="secret456",
            role=service_constants.ROLE_ADMIN,
        )
    )

    all_tenants = tenant_repo.list_all(include_admin=True)
    admin_tenants = [t for t in all_tenants if t.is_admin_tenant]
    assert len(admin_tenants) == 1  # singleton


def test_create_admin_user_does_not_create_agent_profile() -> None:
    """Admin users share a tenant but do not need an agent profile."""
    # Sequence: user_id, admin_tenant_id
    service, _, _, agent_profile_repo = _build_service(["admin-user-id", "admin-tenant-id"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="ignored",
            email="admin@example.com",
            password="secret123",
            role=service_constants.ROLE_ADMIN,
        )
    )

    # The admin tenant ID is "admin-tenant-id"
    profile = agent_profile_repo.get_by_tenant_id("admin-tenant-id")
    assert profile is None


def test_create_professional_role_creates_own_tenant() -> None:
    # Sequence for professional: tenant_id first, then user_id (original behavior)
    service, tenant_repo, user_repo, _ = _build_service(["prof-tenant-id", "prof-user-id"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="My Clinic",
            email="doc@clinic.com",
            password="secret123",
            role=service_constants.ROLE_PROFESSIONAL,
        )
    )

    user = user_repo.get_by_email("doc@clinic.com")
    assert user is not None
    assert user.role == service_constants.ROLE_PROFESSIONAL

    tenant = tenant_repo.get_by_id("prof-tenant-id")
    assert tenant is not None
    assert tenant.is_admin_tenant is False
    assert tenant.name == "My Clinic"


def test_create_professional_duplicate_email_raises() -> None:
    # Sequence: user1_id, tenant1_id, user2_id (duplicate email fails before tenant creation)
    service, _, _, _ = _build_service(["u1", "t1", "u2"])

    service.create_professional(
        user_admin_dto.CreateProfessionalDTO(
            tenant_name="Clinic A",
            email="doc@example.com",
            password="password123",
        )
    )

    with pytest.raises(service_exceptions.InvalidStateError, match="email is already registered"):
        service.create_professional(
            user_admin_dto.CreateProfessionalDTO(
                tenant_name="Clinic B",
                email="doc@example.com",
                password="password456",
            )
        )
