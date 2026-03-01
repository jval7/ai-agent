import datetime

import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.onboarding_status_service as onboarding_status_service
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service
import tests.fakes.fake_adapters as fake_adapters


def build_service() -> onboarding_status_service.OnboardingStatusService:
    store = in_memory_store.InMemoryStore()
    whatsapp_connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    google_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["state-1"])
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    google_provider = fake_adapters.FakeGoogleCalendarProvider()

    whatsapp_service = whatsapp_onboarding_service.WhatsappOnboardingService(
        whatsapp_connection_repository=whatsapp_connection_repository,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        webhook_verify_token="verify-token",
    )
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=google_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )

    whatsapp_connection_repository.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    google_connection_repository.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            connected_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    return onboarding_status_service.OnboardingStatusService(
        whatsapp_onboarding_service=whatsapp_service,
        google_calendar_onboarding_service=google_service,
    )


def test_get_status_returns_ready_when_both_connected() -> None:
    service = build_service()

    status = service.get_status("tenant-1")

    assert status.whatsapp_connected is True
    assert status.google_calendar_connected is True
    assert status.ready is True
