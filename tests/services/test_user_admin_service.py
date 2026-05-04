import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.email_notifier_adapter as email_notifier_adapter
import src.adapters.outbound.inmemory.invitation_token_repository_adapter as invitation_token_repository_adapter
import src.adapters.outbound.inmemory.refresh_token_repository_adapter as refresh_token_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.domain.entities.user as user_entity
import src.services.dto.user_admin_dto as user_admin_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service_mod
import src.services.use_cases.invitation_service as invitation_service_mod
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


def build_user_admin_service_with_invitation(
    id_values: list[str],
) -> tuple[
    user_admin_service.UserAdminService,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    user_repository_adapter.InMemoryUserRepositoryAdapter,
    email_notifier_adapter.FakeEmailNotifierAdapter,
]:
    store = in_memory_store.InMemoryStore()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    refresh_token_repo = refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter()
    invitation_token_repo = (
        invitation_token_repository_adapter.InMemoryInvitationTokenRepositoryAdapter()
    )
    notifier = email_notifier_adapter.FakeEmailNotifierAdapter()
    password_hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_gen = fake_adapters.SequenceIdGenerator(id_values)
    jwt = jwt_provider_adapter.Hs256JwtProviderAdapter(secret="test-secret", clock=clock)

    auth_svc = auth_service_mod.AuthService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=password_hasher,
        jwt_provider=jwt,
        refresh_token_repository=refresh_token_repo,
        id_generator=id_gen,
        clock=clock,
        default_system_prompt="default-prompt",
        access_ttl_seconds=600,
        refresh_ttl_seconds=3600,
    )
    inv_service = invitation_service_mod.InvitationService(
        invitation_token_repository=invitation_token_repo,
        user_repository=user_repo,
        tenant_repository=tenant_repo,
        password_hasher=password_hasher,
        email_notifier=notifier,
        id_generator=id_gen,
        clock=clock,
        refresh_token_repository=refresh_token_repo,
        auth_service=auth_svc,
        frontend_app_base_url="http://localhost:5173",
        account_setup_ttl_hours=168,
        password_reset_ttl_minutes=30,
    )
    service = user_admin_service.UserAdminService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=password_hasher,
        id_generator=id_gen,
        clock=clock,
        default_system_prompt="default-prompt",
        invitation_service=inv_service,
    )
    return service, tenant_repo, user_repo, notifier


def test_invite_professional_creates_user_inactive_and_emits_invitation() -> None:
    service, tenant_repo, user_repo, notifier = build_user_admin_service_with_invitation(
        ["tenant-1", "user-1", "jti-1"]
    )

    service.invite_professional(
        user_admin_dto.InviteProfessionalDTO(
            tenant_name="Acme",
            email="doc@acme.com",
        )
    )

    tenant = tenant_repo.get_by_id("tenant-1")
    user = user_repo.get_by_email("doc@acme.com")
    assert tenant is not None
    assert tenant.name == "Acme"
    assert user is not None
    assert user.is_active is False
    assert len(notifier.sent_emails) == 1
    sent = notifier.sent_emails[0]
    assert sent.kind == "account_invitation"
    assert sent.to_email == "doc@acme.com"
    assert sent.url is not None
    assert "/accept-invite?token=" in sent.url


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
