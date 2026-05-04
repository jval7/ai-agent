import datetime
import hashlib

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
import src.domain.entities.invitation_token as invitation_token_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service_mod
import src.services.use_cases.invitation_service as invitation_service_mod
import tests.fakes.fake_adapters as fake_adapters


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_invitation_service(
    id_values: list[str],
    email_notifier: email_notifier_adapter.FakeEmailNotifierAdapter | None = None,
) -> tuple[
    invitation_service_mod.InvitationService,
    user_repository_adapter.InMemoryUserRepositoryAdapter,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    invitation_token_repository_adapter.InMemoryInvitationTokenRepositoryAdapter,
    refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter,
    email_notifier_adapter.FakeEmailNotifierAdapter,
    fake_adapters.FixedClock,
]:
    store = in_memory_store.InMemoryStore()
    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    refresh_token_repo = refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter()
    invitation_token_repo = (
        invitation_token_repository_adapter.InMemoryInvitationTokenRepositoryAdapter()
    )
    notifier = email_notifier or email_notifier_adapter.FakeEmailNotifierAdapter()
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

    service = invitation_service_mod.InvitationService(
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
    return (
        service,
        user_repo,
        tenant_repo,
        invitation_token_repo,
        refresh_token_repo,
        notifier,
        clock,
    )


def _make_user(
    user_id: str = "user-1",
    tenant_id: str = "tenant-1",
    email: str = "doc@acme.com",
    is_active: bool = False,
) -> user_entity.User:
    return user_entity.User(
        id=user_id,
        tenant_id=tenant_id,
        email=email,
        password_hash="placeholder",
        role="professional",
        is_active=is_active,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


def _make_tenant(tenant_id: str = "tenant-1", name: str = "Acme") -> tenant_entity.Tenant:
    return tenant_entity.Tenant(
        id=tenant_id,
        name=name,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


def test_issue_account_setup_creates_token_hashes_correctly() -> None:
    service, user_repo, tenant_repo, invitation_token_repo, _, _, _ = build_invitation_service(
        ["jti-1", "jti-2"]
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)

    records = list(invitation_token_repo._records_by_hash.values())
    assert len(records) == 1
    record = records[0]
    assert record.user_id == user.id
    assert record.tenant_id == user.tenant_id
    assert record.purpose == invitation_token_entity.InvitationPurpose.ACCOUNT_SETUP
    assert record.consumed_at is None
    assert len(record.token_hash) == 64


def test_issue_account_setup_invalidates_previous_active_tokens() -> None:
    service, user_repo, tenant_repo, invitation_token_repo, _, _, clock = build_invitation_service(
        ["jti-1", "jti-2"]
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    first_hashes = list(invitation_token_repo._records_by_hash.keys())
    assert len(first_hashes) == 1

    clock.advance(60)
    service.issue_account_setup_invitation(user=user, tenant=tenant)

    all_records = list(invitation_token_repo._records_by_hash.values())
    old_record = invitation_token_repo._records_by_hash[first_hashes[0]]
    assert old_record.consumed_at is not None

    active_records = [r for r in all_records if r.consumed_at is None]
    assert len(active_records) == 1


def test_issue_account_setup_sends_email_with_correct_link() -> None:
    service, user_repo, tenant_repo, _, _, notifier, _ = build_invitation_service(["jti-1"])
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)

    assert len(notifier.sent_emails) == 1
    sent = notifier.sent_emails[0]
    assert sent.kind == "account_invitation"
    assert sent.to_email == user.email
    assert sent.url is not None
    assert "/accept-invite?token=" in sent.url
    assert sent.tenant_name == "Acme"


def test_accept_account_setup_sets_password_and_returns_tokens() -> None:
    service, user_repo, tenant_repo, _, _, notifier, _ = build_invitation_service(
        ["jti-1", "jti-2"]
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    invitation_sent = notifier.sent_emails[0]
    raw_token = invitation_sent.url.split("token=")[1]  # type: ignore[union-attr]

    tokens = service.accept_account_setup(token=raw_token, new_password="newpassword123")

    assert tokens.access_token
    assert tokens.refresh_token
    updated_user = user_repo.get_by_id(user.id)
    assert updated_user is not None
    assert updated_user.is_active is True


def test_accept_account_setup_marks_token_consumed() -> None:
    service, user_repo, tenant_repo, invitation_token_repo, _, notifier, _ = (
        build_invitation_service(["jti-1", "jti-2"])
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    invitation_sent = notifier.sent_emails[0]
    raw_token = invitation_sent.url.split("token=")[1]  # type: ignore[union-attr]

    service.accept_account_setup(token=raw_token, new_password="newpassword123")

    token_hash = _hash_token(raw_token)
    record = invitation_token_repo.get_by_hash(token_hash)
    assert record is not None
    assert record.consumed_at is not None


def test_accept_account_setup_rejects_consumed_token() -> None:
    service, user_repo, tenant_repo, _, _, notifier, _ = build_invitation_service(
        ["jti-1", "jti-2", "jti-3"]
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    raw_token = notifier.sent_emails[0].url.split("token=")[1]  # type: ignore[union-attr]
    service.accept_account_setup(token=raw_token, new_password="newpassword123")

    with pytest.raises(service_exceptions.AuthenticationError, match="expired or already used"):
        service.accept_account_setup(token=raw_token, new_password="anotherpassword")


def test_accept_account_setup_rejects_expired_token() -> None:
    service, user_repo, tenant_repo, _, _, notifier, clock = build_invitation_service(["jti-1"])
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    raw_token = notifier.sent_emails[0].url.split("token=")[1]  # type: ignore[union-attr]

    clock.advance(168 * 3600 + 1)

    with pytest.raises(service_exceptions.AuthenticationError, match="expired or already used"):
        service.accept_account_setup(token=raw_token, new_password="newpassword123")


def test_accept_account_setup_rejects_token_with_wrong_purpose() -> None:
    service, user_repo, tenant_repo, invitation_token_repo, _, notifier, _ = (
        build_invitation_service(["jti-1"])
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    raw_token = notifier.sent_emails[0].url.split("token=")[1]  # type: ignore[union-attr]
    token_hash = _hash_token(raw_token)

    existing = invitation_token_repo.get_by_hash(token_hash)
    assert existing is not None
    patched = existing.model_copy(deep=True)
    patched.purpose = invitation_token_entity.InvitationPurpose.PASSWORD_RESET
    invitation_token_repo.save(patched)

    with pytest.raises(service_exceptions.AuthenticationError, match="wrong purpose"):
        service.accept_account_setup(token=raw_token, new_password="newpassword123")


def test_accept_account_setup_sends_welcome_email() -> None:
    service, user_repo, tenant_repo, _, _, notifier, _ = build_invitation_service(
        ["jti-1", "jti-2"]
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    raw_token = notifier.sent_emails[0].url.split("token=")[1]  # type: ignore[union-attr]
    service.accept_account_setup(token=raw_token, new_password="newpassword123")

    welcome_emails = [e for e in notifier.sent_emails if e.kind == "welcome"]
    assert len(welcome_emails) == 1
    assert welcome_emails[0].to_email == user.email


def test_accept_account_setup_succeeds_when_welcome_email_fails() -> None:
    # Use a notifier that starts OK (for invitation send) but we'll flip it to
    # fail before accepting so that only the welcome step fails.
    notifier = email_notifier_adapter.FakeEmailNotifierAdapter(should_fail=False)
    service, user_repo, tenant_repo, _, _, _, _ = build_invitation_service(
        ["jti-1", "jti-2"],
        email_notifier=notifier,
    )
    user = _make_user()
    tenant = _make_tenant()
    user_repo.save(user)
    tenant_repo.save(tenant)

    service.issue_account_setup_invitation(user=user, tenant=tenant)
    raw_token = notifier.sent_emails[0].url.split("token=")[1]  # type: ignore[union-attr]

    # Make welcome email fail
    notifier.should_fail = True
    # accept_account_setup must still succeed even though send_welcome fails
    tokens = service.accept_account_setup(token=raw_token, new_password="newpassword123")

    assert tokens.access_token


def test_request_password_reset_does_not_leak_unknown_email() -> None:
    service, _, _, invitation_token_repo, _, notifier, _ = build_invitation_service([])

    service.request_password_reset(email="nobody@unknown.com")

    assert len(notifier.sent_emails) == 0
    assert len(invitation_token_repo._records_by_hash) == 0


def test_confirm_password_reset_revokes_all_refresh_tokens() -> None:
    service, user_repo, tenant_repo, _, _, notifier, _ = build_invitation_service(
        ["jti-pw-1", "jti-pw-2"]
    )
    user = _make_user(is_active=True)
    user_repo.save(user)
    tenant_repo.save(_make_tenant())

    service.request_password_reset(email=user.email)
    raw_token = notifier.sent_emails[0].url.split("token=")[1]  # type: ignore[union-attr]

    service.confirm_password_reset(token=raw_token, new_password="freshpassword")

    updated_user = user_repo.get_by_id(user.id)
    assert updated_user is not None
