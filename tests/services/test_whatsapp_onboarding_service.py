import datetime
import logging

import pytest

import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service
import tests.fakes.fake_adapters as fake_adapters

LOGGER_NAME = "src.services.use_cases.whatsapp_onboarding_service"


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
        meta_app_id="test-app-id",
        meta_config_id="test-config-id",
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
    assert provider.waba_subscriptions == [
        {
            "access_token": "token-1",
            "business_account_id": "business-1",
        }
    ]
    assert provider.phone_registrations == [
        {
            "access_token": "token-1",
            "phone_number_id": "phone-1",
        }
    ]


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


def test_complete_embedded_signup_fails_when_meta_subscription_fails() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    provider.should_fail_subscription = True
    session_response = service.create_embedded_signup_session("tenant-1")

    with pytest.raises(service_exceptions.ExternalProviderError):
        service.complete_embedded_signup(
            "tenant-1",
            whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state=session_response.state),
        )

    status = service.get_connection_status("tenant-1")
    assert status.status == "PENDING"
    assert status.phone_number_id is None


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


def test_create_session_logs_session_created(caplog: pytest.LogCaptureFixture) -> None:
    service, _ = build_onboarding_service(["state-1"])
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    service.create_embedded_signup_session("tenant-1")

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "whatsapp.onboarding.session_created" in events


def test_complete_embedded_signup_with_direct_access_token() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-direct",
    )

    session_response = service.create_embedded_signup_session("tenant-1")
    complete_response = service.complete_embedded_signup(
        "tenant-1",
        whatsapp_dto.EmbeddedSignupCompleteDTO(
            access_token="token-direct", state=session_response.state
        ),
    )

    assert complete_response.status == "CONNECTED"
    assert complete_response.phone_number_id == "phone-1"
    assert provider.waba_subscriptions == [
        {"access_token": "token-direct", "business_account_id": "business-1"}
    ]
    assert provider.phone_registrations == [
        {"access_token": "token-direct", "phone_number_id": "phone-1"}
    ]


def test_complete_embedded_signup_fails_when_neither_code_nor_token() -> None:
    service, _ = build_onboarding_service(["state-1"])
    session_response = service.create_embedded_signup_session("tenant-1")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.complete_embedded_signup(
            "tenant-1",
            whatsapp_dto.EmbeddedSignupCompleteDTO(state=session_response.state),
        )


def test_complete_state_mismatch_logs_failure(caplog: pytest.LogCaptureFixture) -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    service.create_embedded_signup_session("tenant-1")
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    with pytest.raises(service_exceptions.InvalidStateError):
        service.complete_embedded_signup(
            "tenant-1",
            whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state="wrong-state"),
        )

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "whatsapp.onboarding.failed" in events


# ---------------------------------------------------------------------------
# complete_embedded_signup error paths + verify_webhook + register tolerance
# ---------------------------------------------------------------------------


def test_complete_embedded_signup_raises_when_no_session_for_tenant() -> None:
    service, _ = build_onboarding_service([])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.complete_embedded_signup(
            "tenant-without-session",
            whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-x", state="state-x"),
        )


def test_finalize_connection_tolerates_smb_register_error() -> None:
    service, provider = build_onboarding_service(["state-1"])
    provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )

    class _SmbProvider(fake_adapters.FakeWhatsappProvider):
        def register_phone_number(
            self, access_token: str, phone_number_id: str, registration_pin: str | None = None
        ) -> None:
            del access_token, phone_number_id, registration_pin
            raise service_exceptions.ExternalProviderError(
                "(#136025) Phone number registration not available for SMB accounts"
            )

    smb_provider = _SmbProvider()
    smb_provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    service._whatsapp_provider = smb_provider
    session_response = service.create_embedded_signup_session("tenant-1")
    response = service.complete_embedded_signup(
        "tenant-1",
        whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state=session_response.state),
    )

    # Connection is still saved as CONNECTED — SMB error is tolerated.
    assert response.status == "CONNECTED"


def test_finalize_connection_tolerates_pin_required_register_error() -> None:
    service, _ = build_onboarding_service(["state-1"])

    class _PinRequiredProvider(fake_adapters.FakeWhatsappProvider):
        def register_phone_number(
            self, access_token: str, phone_number_id: str, registration_pin: str | None = None
        ) -> None:
            del access_token, phone_number_id, registration_pin
            raise service_exceptions.ExternalProviderError(
                "Two-step verification PIN is required for this number"
            )

    pin_provider = _PinRequiredProvider()
    pin_provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    service._whatsapp_provider = pin_provider
    session_response = service.create_embedded_signup_session("tenant-1")
    response = service.complete_embedded_signup(
        "tenant-1",
        whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state=session_response.state),
    )

    assert response.status == "CONNECTED"


def test_finalize_connection_propagates_other_register_errors() -> None:
    service, _ = build_onboarding_service(["state-1"])

    class _UnknownErrorProvider(fake_adapters.FakeWhatsappProvider):
        def register_phone_number(
            self, access_token: str, phone_number_id: str, registration_pin: str | None = None
        ) -> None:
            del access_token, phone_number_id, registration_pin
            raise service_exceptions.ExternalProviderError("Some other registration error")

    unknown_provider = _UnknownErrorProvider()
    unknown_provider.credential_by_code["code-1"] = whatsapp_dto.EmbeddedSignupCredentialsDTO(
        phone_number_id="phone-1",
        business_account_id="business-1",
        access_token="token-1",
    )
    service._whatsapp_provider = unknown_provider
    session_response = service.create_embedded_signup_session("tenant-1")

    with pytest.raises(service_exceptions.ExternalProviderError):
        service.complete_embedded_signup(
            "tenant-1",
            whatsapp_dto.EmbeddedSignupCompleteDTO(code="code-1", state=session_response.state),
        )


def test_verify_webhook_rejects_invalid_mode() -> None:
    service, _ = build_onboarding_service([], webhook_verify_token="verify-global")

    with pytest.raises(service_exceptions.AuthorizationError):
        service.verify_webhook(
            webhook_dto.WebhookVerificationDTO(
                mode="unsubscribe",
                verify_token="verify-global",
                challenge="ok-challenge",
            )
        )


def test_verify_webhook_raises_when_verify_token_not_configured() -> None:
    service, _ = build_onboarding_service([], webhook_verify_token="")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.verify_webhook(
            webhook_dto.WebhookVerificationDTO(
                mode="subscribe",
                verify_token="anything",
                challenge="ok-challenge",
            )
        )


def test_verify_webhook_rejects_invalid_verify_token() -> None:
    service, _ = build_onboarding_service([], webhook_verify_token="verify-global")

    with pytest.raises(service_exceptions.AuthorizationError):
        service.verify_webhook(
            webhook_dto.WebhookVerificationDTO(
                mode="subscribe",
                verify_token="wrong-token",
                challenge="ok-challenge",
            )
        )
