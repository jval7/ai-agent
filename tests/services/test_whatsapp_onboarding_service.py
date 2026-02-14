import datetime

import pytest

import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service
import tests.fakes.fake_adapters as fake_adapters


def build_onboarding_service(
    id_values: list[str],
    webhook_verify_token: str | None = None,
) -> tuple[
    whatsapp_onboarding_service.WhatsappOnboardingService,
    fake_adapters.FakeWhatsappProvider,
]:
    store = in_memory_store.InMemoryStore()
    connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    resolved_webhook_verify_token = webhook_verify_token
    if resolved_webhook_verify_token is None:
        resolved_webhook_verify_token = "global-verify-token"

    service = whatsapp_onboarding_service.WhatsappOnboardingService(
        whatsapp_connection_repository=connection_repository,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        webhook_verify_token=resolved_webhook_verify_token,
    )
    return service, provider


def test_create_session_and_complete_embedded_signup() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )

    session_response = service.create_embedded_signup_session("tenant-1")
    complete_response = service.complete_embedded_signup(
        "tenant-1",
        whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state=session_response.state),
    )

    assert session_response.connect_url.endswith("state=state-1")
    assert complete_response.status == "CONNECTED"
    assert complete_response.phone_number_id == "phone-1"


def test_verify_webhook_validates_verify_token() -> None:
    service, _ = build_onboarding_service(["state-1"], webhook_verify_token="verify-global")

    challenge = service.verify_webhook(
        webhook_dto.WebhookVerificationDTO(
            mode="subscribe",
            verify_token="verify-global",
            challenge="ok-challenge",
        )
    )

    assert challenge == "ok-challenge"


def test_complete_embedded_signup_fails_when_state_mismatch() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    service.create_embedded_signup_session("tenant-1")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.complete_embedded_signup(
            "tenant-1",
            whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state="wrong-state"),
        )


def test_complete_embedded_signup_by_state_finishes_connection() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    service.create_embedded_signup_session("tenant-1")

    result = service.complete_embedded_signup_by_state(code="code-1", state="state-1")

    assert result.tenant_id == "tenant-1"
    assert result.status == "CONNECTED"
    assert result.phone_number_id == "phone-1"


def test_complete_embedded_signup_by_state_fails_when_state_not_found() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.complete_embedded_signup_by_state(code="code-1", state="unknown-state")


def test_get_connection_status_returns_disconnected_when_not_configured() -> None:
    service, _ = build_onboarding_service(["state-1"])

    status = service.get_connection_status("tenant-1")

    assert status.status == "DISCONNECTED"
    assert status.phone_number_id is None


def test_get_dev_verify_token_returns_global_token() -> None:
    service, _ = build_onboarding_service(["state-1"], webhook_verify_token="verify-global")

    result = service.get_dev_verify_token()

    assert result.verify_token == "verify-global"


def test_get_dev_verify_token_fails_when_token_is_missing() -> None:
    service, _ = build_onboarding_service(["state-1"], webhook_verify_token="")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.get_dev_verify_token()
