import datetime

import pytest

import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import tests.fakes.fake_adapters as fake_adapters


def build_service(
    id_values: list[str],
) -> tuple[
    google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
]:
    store = in_memory_store.InMemoryStore()
    repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(id_values)

    service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=repository,
        google_calendar_provider=provider,
        id_generator=id_generator,
        clock=clock,
    )
    return service, repository, provider


def test_create_oauth_session_and_complete_oauth() -> None:
    service, repository, provider = build_service(["state-1"])
    provider.tokens_by_code["code-1"] = google_calendar_dto.GoogleOauthTokensDTO(
        access_token="access-1",
        refresh_token="refresh-1",
        expires_in_seconds=3600,
        scope="calendar",
        token_type="Bearer",
    )

    session = service.create_oauth_session(tenant_id="tenant-1", professional_user_id="user-1")
    assert session.state == "state-1"
    assert "state=state-1" in session.connect_url

    completed = service.complete_oauth(
        tenant_id="tenant-1",
        professional_user_id="user-1",
        complete_dto=google_calendar_dto.GoogleOauthCompleteDTO(code="code-1", state="state-1"),
    )

    assert completed.status == "CONNECTED"
    assert completed.calendar_id == "primary"
    assert completed.professional_timezone == "America/Bogota"
    stored = repository.get_by_tenant_id("tenant-1")
    assert stored is not None
    assert stored.oauth_state is None
    assert stored.refresh_token == "refresh-1"


def test_complete_oauth_rejects_invalid_state() -> None:
    service, _, _ = build_service(["state-1"])
    service.create_oauth_session(tenant_id="tenant-1", professional_user_id="user-1")

    with pytest.raises(service_exceptions.InvalidStateError):
        service.complete_oauth(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            complete_dto=google_calendar_dto.GoogleOauthCompleteDTO(
                code="code-1",
                state="state-2",
            ),
        )


def test_get_availability_refreshes_expired_token() -> None:
    service, repository, provider = build_service(["state-1"])
    provider.tokens_by_code["code-1"] = google_calendar_dto.GoogleOauthTokensDTO(
        access_token="access-1",
        refresh_token="refresh-1",
        expires_in_seconds=1,
        scope="calendar",
        token_type="Bearer",
    )
    provider.refreshed_tokens_by_refresh_token["refresh-1"] = (
        google_calendar_dto.GoogleOauthTokensDTO(
            access_token="access-2",
            refresh_token=None,
            expires_in_seconds=3600,
            scope="calendar",
            token_type="Bearer",
        )
    )

    service.create_oauth_session(tenant_id="tenant-1", professional_user_id="user-1")
    service.complete_oauth(
        tenant_id="tenant-1",
        professional_user_id="user-1",
        complete_dto=google_calendar_dto.GoogleOauthCompleteDTO(code="code-1", state="state-1"),
    )
    stored_before = repository.get_by_tenant_id("tenant-1")
    assert stored_before is not None
    assert stored_before.access_token == "access-1"

    availability = service.get_availability(
        tenant_id="tenant-1",
        from_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
        to_at=datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC),
    )
    assert availability.calendar_id == "primary"
    stored_after = repository.get_by_tenant_id("tenant-1")
    assert stored_after is not None
    assert stored_after.access_token == "access-2"
