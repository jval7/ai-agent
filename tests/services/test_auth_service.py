import datetime
import logging

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service
import tests.fakes.fake_adapters as fake_adapters

LOGGER_NAME = "src.services.use_cases.auth_service"


def build_auth_service(
    id_values: list[str],
) -> tuple[
    auth_service.AuthService,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    user_repository_adapter.InMemoryUserRepositoryAdapter,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
    jwt_provider_adapter.Hs256JwtProviderAdapter,
]:
    store = in_memory_store.InMemoryStore()
    tenant_repository = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repository = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repository = (
        agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    )

    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    password_hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    jwt_provider = jwt_provider_adapter.Hs256JwtProviderAdapter(secret="test-secret", clock=clock)

    service = auth_service.AuthService(
        tenant_repository=tenant_repository,
        user_repository=user_repository,
        agent_profile_repository=agent_profile_repository,
        password_hasher=password_hasher,
        jwt_provider=jwt_provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default-prompt",
        access_ttl_seconds=600,
        refresh_ttl_seconds=3600,
    )
    return service, tenant_repository, user_repository, agent_profile_repository, jwt_provider


def test_register_creates_tenant_user_and_default_prompt() -> None:
    service, tenant_repository, user_repository, agent_profile_repository, jwt_provider = (
        build_auth_service(["tenant-1", "user-1", "access-jti-1", "refresh-jti-1"])
    )

    result = service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )

    tenant = tenant_repository.get_by_id("tenant-1")
    user = user_repository.get_by_email("owner@acme.com")
    agent_profile = agent_profile_repository.get_by_tenant_id("tenant-1")
    access_claims = jwt_provider.decode(result.access_token)
    refresh_claims = jwt_provider.decode(result.refresh_token)

    assert tenant is not None
    assert user is not None
    assert agent_profile is not None
    assert access_claims.tenant_id == "tenant-1"
    assert access_claims.token_kind == "access"
    assert refresh_claims.token_kind == "refresh"


def test_login_rejects_invalid_password() -> None:
    service, _, _, _, _ = build_auth_service(
        [
            "tenant-1",
            "user-1",
            "access-jti-1",
            "refresh-jti-1",
            "access-jti-2",
            "refresh-jti-2",
        ]
    )
    service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )

    with pytest.raises(service_exceptions.AuthenticationError):
        service.login(auth_dto.LoginDTO(email="owner@acme.com", password="wrongpassword"))


def test_login_returns_tokens_for_valid_credentials() -> None:
    service, _, _, _, jwt_provider = build_auth_service(
        [
            "tenant-1",
            "user-1",
            "access-jti-1",
            "refresh-jti-1",
            "access-jti-2",
            "refresh-jti-2",
        ]
    )
    service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )

    result = service.login(auth_dto.LoginDTO(email="owner@acme.com", password="supersecret"))
    access_claims = jwt_provider.decode(result.access_token)
    refresh_claims = jwt_provider.decode(result.refresh_token)

    assert access_claims.token_kind == "access"
    assert refresh_claims.token_kind == "refresh"


def test_refresh_rotates_refresh_token_and_revokes_previous() -> None:
    service, _, _, _, _ = build_auth_service(
        [
            "tenant-1",
            "user-1",
            "access-jti-1",
            "refresh-jti-1",
            "access-jti-2",
            "refresh-jti-2",
        ]
    )

    register_result = service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )

    refreshed_tokens = service.refresh(
        auth_dto.RefreshTokenDTO(refresh_token=register_result.refresh_token)
    )

    assert refreshed_tokens.refresh_token != register_result.refresh_token

    with pytest.raises(service_exceptions.AuthenticationError):
        service.refresh(auth_dto.RefreshTokenDTO(refresh_token=register_result.refresh_token))


def test_logout_revokes_refresh_token() -> None:
    service, _, _, _, _ = build_auth_service(
        [
            "tenant-1",
            "user-1",
            "access-jti-1",
            "refresh-jti-1",
        ]
    )

    register_result = service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )

    service.logout(auth_dto.LogoutDTO(refresh_token=register_result.refresh_token))

    with pytest.raises(service_exceptions.AuthenticationError):
        service.refresh(auth_dto.RefreshTokenDTO(refresh_token=register_result.refresh_token))


def test_register_emits_success_log_without_sensitive_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, _, _, _, _ = build_auth_service(
        ["tenant-1", "user-1", "access-jti-1", "refresh-jti-1"]
    )
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )

    event_names = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "auth.register.success" in event_names

    for record in caplog.records:
        event_data = record.__dict__.get("event_data")
        if not isinstance(event_data, dict):
            continue
        assert "password" not in event_data
        assert "access_token" not in event_data
        assert "refresh_token" not in event_data


def test_login_failure_emits_failed_log(caplog: pytest.LogCaptureFixture) -> None:
    service, _, _, _, _ = build_auth_service(
        [
            "tenant-1",
            "user-1",
            "access-jti-1",
            "refresh-jti-1",
            "access-jti-2",
            "refresh-jti-2",
        ]
    )
    service.register(
        auth_dto.RegisterUserDTO(
            tenant_name="Acme",
            email="owner@acme.com",
            password="supersecret",
        )
    )
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    with pytest.raises(service_exceptions.AuthenticationError):
        service.login(auth_dto.LoginDTO(email="owner@acme.com", password="wrongpassword"))

    failure_events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "auth.login.failed" in failure_events
