import datetime
import pathlib
import tempfile

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.services.dto.auth_dto as auth_dto
import src.services.use_cases.auth_service as auth_service
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service
import tests.fakes.fake_adapters as fake_adapters


def build_services(
    memory_snapshot_path: str,
    id_values: list[str],
    webhook_verify_token: str | None = None,
) -> tuple[
    auth_service.AuthService,
    whatsapp_onboarding_service.WhatsappOnboardingService,
    jwt_provider_adapter.Hs256JwtProviderAdapter,
]:
    store = in_memory_store.InMemoryStore(persistence_file_path=memory_snapshot_path)

    tenant_repository = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repository = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repository = (
        agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    )
    whatsapp_connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )

    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    password_hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    jwt_provider = jwt_provider_adapter.Hs256JwtProviderAdapter(secret="test-secret", clock=clock)
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    resolved_webhook_verify_token = webhook_verify_token
    if resolved_webhook_verify_token is None:
        resolved_webhook_verify_token = "global-verify-token"

    auth = auth_service.AuthService(
        tenant_repository=tenant_repository,
        user_repository=user_repository,
        agent_profile_repository=agent_profile_repository,
        password_hasher=password_hasher,
        jwt_provider=jwt_provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default-prompt",
        access_ttl_seconds=1800,
        refresh_ttl_seconds=2592000,
    )

    onboarding = whatsapp_onboarding_service.WhatsappOnboardingService(
        whatsapp_connection_repository=whatsapp_connection_repository,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        webhook_verify_token=resolved_webhook_verify_token,
    )

    return auth, onboarding, jwt_provider


def test_domain_state_persists_across_restart_with_json_memory() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot_path = str(pathlib.Path(temp_dir) / "memory_store.json")

        auth_first_boot, onboarding_first_boot, jwt_provider_first_boot = build_services(
            snapshot_path,
            [
                "tenant-1",
                "user-1",
                "access-jti-1",
                "refresh-jti-1",
                "state-1",
            ],
        )

        register_result = auth_first_boot.register(
            auth_dto.RegisterUserDTO(
                tenant_name="Acme",
                email="owner@acme.com",
                password="supersecret",
            )
        )
        first_boot_claims = jwt_provider_first_boot.decode(register_result.access_token)

        first_session = onboarding_first_boot.create_embedded_signup_session(
            first_boot_claims.tenant_id
        )
        first_verify_token = onboarding_first_boot.get_dev_verify_token().verify_token

        assert pathlib.Path(snapshot_path).exists()
        assert first_session.state == "state-1"

        auth_second_boot, onboarding_second_boot, _ = build_services(
            snapshot_path,
            [
                "access-jti-2",
                "refresh-jti-2",
            ],
        )

        login_result = auth_second_boot.login(
            auth_dto.LoginDTO(
                email="owner@acme.com",
                password="supersecret",
            )
        )
        second_boot_claims = auth_second_boot.authenticate_access_token(login_result.access_token)
        second_verify_token = onboarding_second_boot.get_dev_verify_token().verify_token
        second_status = onboarding_second_boot.get_connection_status(second_boot_claims.tenant_id)

        assert second_verify_token == first_verify_token
        assert second_status.status == "PENDING"
