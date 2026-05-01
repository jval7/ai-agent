import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.refresh_token_repository_adapter as refresh_token_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.domain.entities.tenant as tenant_entity
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service_mod
import src.services.use_cases.eval_tenant_service as eval_tenant_service
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_service(
    id_values: list[str] | None = None,
) -> tuple[
    eval_tenant_service.EvalTenantService,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    user_repository_adapter.InMemoryUserRepositoryAdapter,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
    whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
]:
    if id_values is None:
        # Provide enough IDs for: tenant_id, user_id in create + jti for access + jti for refresh
        id_values = ["tenant-1", "user-1", "jti-access-1", "jti-refresh-1"]

    store = in_memory_store.InMemoryStore()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    wa_repo = whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(
        store
    )
    refresh_token_repo = refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter()

    clock = fake_adapters.FixedClock(_NOW)
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    jwt_provider = jwt_provider_adapter.Hs256JwtProviderAdapter(secret="test-secret", clock=clock)

    auth_svc = auth_service_mod.AuthService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=hasher,
        jwt_provider=jwt_provider,
        refresh_token_repository=refresh_token_repo,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="test-prompt",
        access_ttl_seconds=600,
        refresh_ttl_seconds=3600,
    )

    service = eval_tenant_service.EvalTenantService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        whatsapp_connection_repository=wa_repo,
        password_hasher=hasher,
        auth_service=auth_svc,
        id_generator=id_generator,
        clock=clock,
    )
    return service, tenant_repo, user_repo, agent_profile_repo, wa_repo


def test_create_eval_tenant_creates_all_entities() -> None:
    service, tenant_repo, user_repo, agent_profile_repo, wa_repo = _build_service()

    result = service.create_eval_tenant(run_id="run-abc", shape_name="psicologa")

    # Tenant exists with is_eval_tenant=True
    tenant = tenant_repo.get_by_id(result.tenant_id)
    assert tenant is not None
    assert tenant.is_eval_tenant is True
    assert tenant.id == "tenant-1"

    # User exists with matching email
    assert result.email == "eval-psicologa-run-abc@eval.local"
    user = user_repo.get_by_email(result.email)
    assert user is not None
    assert user.tenant_id == result.tenant_id
    assert user.is_active is True
    assert user.role == "professional"

    # AgentProfile exists
    profile = agent_profile_repo.get_by_tenant_id(result.tenant_id)
    assert profile is not None
    assert profile.tenant_id == result.tenant_id

    # WhatsApp connection exists with correct phone_number_id
    assert result.phone_number_id == "mock_eval_run-abc_psicologa"
    wa_conn = wa_repo.get_by_tenant_id(result.tenant_id)
    assert wa_conn is not None
    assert wa_conn.phone_number_id == result.phone_number_id
    assert wa_conn.status == "CONNECTED"

    # Phone index is resolvable
    wa_by_phone = wa_repo.get_by_phone_number_id(result.phone_number_id)
    assert wa_by_phone is not None
    assert wa_by_phone.tenant_id == result.tenant_id

    # Tokens are non-empty strings
    assert result.access_token
    assert result.refresh_token


def test_delete_eval_tenant_cascade() -> None:
    service, tenant_repo, user_repo, agent_profile_repo, wa_repo = _build_service()

    result = service.create_eval_tenant(run_id="run-del", shape_name="ortodoncista")
    tenant_id = result.tenant_id
    phone_number_id = result.phone_number_id

    # Verify entities exist before delete
    assert tenant_repo.get_by_id(tenant_id) is not None
    assert wa_repo.get_by_phone_number_id(phone_number_id) is not None

    service.delete_eval_tenant(tenant_id)

    # Tenant must be gone
    assert tenant_repo.get_by_id(tenant_id) is None
    # User must be gone
    assert user_repo.get_by_email(result.email) is None
    # Agent profile must be gone
    assert agent_profile_repo.get_by_tenant_id(tenant_id) is None
    # WA connection and phone index must be gone
    assert wa_repo.get_by_tenant_id(tenant_id) is None
    assert wa_repo.get_by_phone_number_id(phone_number_id) is None


def test_delete_refuses_non_eval_tenant() -> None:
    store = in_memory_store.InMemoryStore()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)

    # Insert a regular tenant (is_eval_tenant=False by default)
    regular_tenant = tenant_entity.Tenant(
        id="regular-tenant",
        name="Real Clinic",
        created_at=_NOW,
        updated_at=_NOW,
        is_eval_tenant=False,
    )
    tenant_repo.save(regular_tenant)

    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    wa_repo = whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(
        store
    )
    refresh_token_repo = refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter()
    clock = fake_adapters.FixedClock(_NOW)
    id_generator = fake_adapters.SequenceIdGenerator(["unused"])
    hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    jwt_provider = jwt_provider_adapter.Hs256JwtProviderAdapter(secret="test-secret", clock=clock)

    auth_svc = auth_service_mod.AuthService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=hasher,
        jwt_provider=jwt_provider,
        refresh_token_repository=refresh_token_repo,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="test-prompt",
        access_ttl_seconds=600,
        refresh_ttl_seconds=3600,
    )

    service = eval_tenant_service.EvalTenantService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        whatsapp_connection_repository=wa_repo,
        password_hasher=hasher,
        auth_service=auth_svc,
        id_generator=id_generator,
        clock=clock,
    )

    with pytest.raises(service_exceptions.InvalidStateError):
        service.delete_eval_tenant("regular-tenant")


def test_delete_eval_tenant_raises_not_found_when_missing() -> None:
    service, *_ = _build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.delete_eval_tenant("nonexistent-tenant-id")
