import datetime
import typing

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.dto.whatsapp_billing_dto as whatsapp_billing_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.whatsapp_billing_service as whatsapp_billing_service_module
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_TENANT_ID = "tenant-1"
_PHONE = "+573001234567"


def _build_context(
    *,
    seed_connection: bool = True,
    connection_status: typing.Literal["DISCONNECTED", "PENDING", "CONNECTED"] = "CONNECTED",
) -> tuple[
    whatsapp_billing_service_module.WhatsappBillingService,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
    fake_adapters.FakeWhatsappProvider,
]:
    store = in_memory_store.InMemoryStore()
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    wa_connection_repo = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    wa_provider = fake_adapters.FakeWhatsappProvider()
    clock = fake_adapters.FixedClock(_NOW)

    if seed_connection:
        wa_connection_repo.save(
            whatsapp_connection_entity.WhatsappConnection(
                tenant_id=_TENANT_ID,
                phone_number_id="phone-1",
                business_account_id="waba-1",
                access_token="wa-token-1",
                status=connection_status,
                embedded_signup_state=None,
                updated_at=_NOW,
            )
        )

    billing_svc = whatsapp_billing_service_module.WhatsappBillingService(
        whatsapp_provider=wa_provider,
        whatsapp_connection_repository=wa_connection_repo,
        agent_profile_repository=agent_profile_repo,
        clock=clock,
    )
    return billing_svc, agent_profile_repo, wa_provider


def _seed_profile(
    agent_profile_repo: agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
) -> None:
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id=_TENANT_ID,
            system_prompt="prompt",
            updated_at=_NOW,
        )
    )


def _request(phone: str = _PHONE) -> whatsapp_billing_dto.BillingPreflightRequestDTO:
    return whatsapp_billing_dto.BillingPreflightRequestDTO(recipient_phone_number=phone)


def test_run_preflight_raises_when_connection_missing() -> None:
    billing_svc, _, _ = _build_context(seed_connection=False)

    with pytest.raises(service_exceptions.EntityNotFoundError):
        billing_svc.run_preflight(_TENANT_ID, _request())


def test_run_preflight_raises_when_connection_not_connected() -> None:
    billing_svc, _, _ = _build_context(connection_status="PENDING")

    with pytest.raises(service_exceptions.InvalidStateError):
        billing_svc.run_preflight(_TENANT_ID, _request())


def test_run_preflight_success_persists_phone_and_returns_ok() -> None:
    billing_svc, agent_profile_repo, wa_provider = _build_context()
    _seed_profile(agent_profile_repo)

    result = billing_svc.run_preflight(_TENANT_ID, _request())

    assert result.ok is True
    assert result.recipient_phone_number == _PHONE
    assert wa_provider.preflight_calls == [
        {
            "access_token": "wa-token-1",
            "phone_number_id": "phone-1",
            "recipient_phone_e164": _PHONE,
        }
    ]
    updated_profile = agent_profile_repo.get_by_tenant_id(_TENANT_ID)
    assert updated_profile is not None
    assert updated_profile.reminder_billing_test_phone_number == _PHONE


def test_run_preflight_success_without_existing_profile_does_not_persist() -> None:
    billing_svc, agent_profile_repo, wa_provider = _build_context()

    result = billing_svc.run_preflight(_TENANT_ID, _request())

    assert result.ok is True
    assert wa_provider.preflight_calls != []
    assert agent_profile_repo.get_by_tenant_id(_TENANT_ID) is None


def test_run_preflight_propagates_billing_not_configured_error() -> None:
    billing_svc, agent_profile_repo, wa_provider = _build_context()
    _seed_profile(agent_profile_repo)
    wa_provider.preflight_errors.append(
        service_exceptions.WhatsappBillingNotConfiguredError("no payment method")
    )

    with pytest.raises(service_exceptions.WhatsappBillingNotConfiguredError):
        billing_svc.run_preflight(_TENANT_ID, _request())

    profile_after = agent_profile_repo.get_by_tenant_id(_TENANT_ID)
    assert profile_after is not None
    assert profile_after.reminder_billing_test_phone_number is None


def test_run_preflight_propagates_other_meta_error() -> None:
    billing_svc, agent_profile_repo, _ = _build_context()
    _seed_profile(agent_profile_repo)

    error = service_exceptions.WhatsappPreflightError("rate limited", meta_error_code=80007)
    billing_svc._whatsapp_provider.preflight_errors.append(error)  # type: ignore[attr-defined]

    with pytest.raises(service_exceptions.WhatsappPreflightError) as exc_info:
        billing_svc.run_preflight(_TENANT_ID, _request())

    assert exc_info.value.meta_error_code == 80007


def test_billing_preflight_request_dto_rejects_invalid_phone() -> None:
    with pytest.raises(ValueError):
        whatsapp_billing_dto.BillingPreflightRequestDTO(recipient_phone_number="12345")
    with pytest.raises(ValueError):
        whatsapp_billing_dto.BillingPreflightRequestDTO(recipient_phone_number="+abc")


def test_billing_preflight_request_dto_accepts_e164() -> None:
    dto = whatsapp_billing_dto.BillingPreflightRequestDTO(recipient_phone_number=" +573001234567 ")
    assert dto.recipient_phone_number == "+573001234567"
