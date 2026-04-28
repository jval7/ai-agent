import datetime

import pytest

import src.domain.entities.tenant as tenant_entity
import src.services.dto.tenant_dto as tenant_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.tenant_profile_service as tenant_profile_service
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _build_tenant(
    tenant_id: str = "tenant-1",
    professional_name: str | None = None,
) -> tenant_entity.Tenant:
    return tenant_entity.Tenant(
        id=tenant_id,
        name="Test Clinic",
        created_at=_NOW,
        updated_at=_NOW,
        professional_name=professional_name,
    )


def build_service() -> tuple[
    tenant_profile_service.TenantProfileService,
    fake_adapters.FakeTenantRepository,
    fake_adapters.FixedClock,
]:
    repo = fake_adapters.FakeTenantRepository()
    clock = fake_adapters.FixedClock(_NOW)
    service = tenant_profile_service.TenantProfileService(
        tenant_repository=repo,
        clock=clock,
    )
    return service, repo, clock


def test_get_profile_returns_dto_with_professional_name() -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant(professional_name="Dr. Ana García"))

    result = service.get_profile("tenant-1")

    assert result.tenant_id == "tenant-1"
    assert result.name == "Test Clinic"
    assert result.professional_name == "Dr. Ana García"


def test_get_profile_returns_none_professional_name_when_not_set() -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant(professional_name=None))

    result = service.get_profile("tenant-1")

    assert result.professional_name is None


def test_get_profile_raises_not_found_for_missing_tenant() -> None:
    service, _, _ = build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.get_profile("nonexistent-tenant")


def test_update_profile_persists_professional_name() -> None:
    service, repo, clock = build_service()
    repo.save(_build_tenant())
    clock.advance(60)

    result = service.update_profile(
        "tenant-1",
        tenant_dto.UpdateTenantProfileDTO(professional_name="Dr. Jhon Valderrama"),
    )

    assert result.professional_name == "Dr. Jhon Valderrama"
    stored = repo.get_by_id("tenant-1")
    assert stored is not None
    assert stored.professional_name == "Dr. Jhon Valderrama"
    assert stored.updated_at > _NOW


def test_update_profile_clears_professional_name_when_none() -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant(professional_name="Old Name"))

    result = service.update_profile(
        "tenant-1",
        tenant_dto.UpdateTenantProfileDTO(professional_name=None),
    )

    assert result.professional_name is None
    stored = repo.get_by_id("tenant-1")
    assert stored is not None
    assert stored.professional_name is None


def test_update_profile_raises_not_found_for_missing_tenant() -> None:
    service, _, _ = build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.update_profile(
            "nonexistent-tenant",
            tenant_dto.UpdateTenantProfileDTO(professional_name="Dr. X"),
        )


def test_get_profile_returns_default_session_duration() -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant())

    result = service.get_profile("tenant-1")

    assert result.session_duration_minutes == 60


def test_update_profile_persists_valid_session_duration() -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant())

    result = service.update_profile(
        "tenant-1",
        tenant_dto.UpdateTenantProfileDTO(professional_name=None, session_duration_minutes=45),
    )

    assert result.session_duration_minutes == 45
    stored = repo.get_by_id("tenant-1")
    assert stored is not None
    assert stored.session_duration_minutes == 45


def test_update_profile_keeps_existing_duration_when_none_provided() -> None:
    service, repo, _ = build_service()
    repo.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Clinic",
            created_at=_NOW,
            updated_at=_NOW,
            session_duration_minutes=30,
        )
    )

    result = service.update_profile(
        "tenant-1",
        tenant_dto.UpdateTenantProfileDTO(professional_name="Dr. X", session_duration_minutes=None),
    )

    assert result.session_duration_minutes == 30


@pytest.mark.parametrize("duration", [15, 30, 45, 60, 90, 120])  # type: ignore[misc, unused-ignore]
def test_update_profile_accepts_all_valid_preset_durations(duration: int) -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant())

    result = service.update_profile(
        "tenant-1",
        tenant_dto.UpdateTenantProfileDTO(
            professional_name=None, session_duration_minutes=duration
        ),
    )

    assert result.session_duration_minutes == duration


@pytest.mark.parametrize("invalid_duration", [0, 10, 20, 25, 50, 75, 100, 150, -1])  # type: ignore[misc, unused-ignore]
def test_update_profile_rejects_invalid_session_duration(invalid_duration: int) -> None:
    service, repo, _ = build_service()
    repo.save(_build_tenant())

    with pytest.raises(service_exceptions.InvalidStateError):
        service.update_profile(
            "tenant-1",
            tenant_dto.UpdateTenantProfileDTO(
                professional_name=None, session_duration_minutes=invalid_duration
            ),
        )


def test_get_professional_name_reads_from_tenant_repo() -> None:
    """Verify GoogleCalendarOnboardingService.get_professional_name reads from Tenant."""
    import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as gcal_repo
    import src.adapters.outbound.inmemory.store as in_memory_store
    import src.services.use_cases.google_calendar_onboarding_service as gcal_service

    store = in_memory_store.InMemoryStore()
    calendar_connection_repo = gcal_repo.InMemoryGoogleCalendarConnectionRepositoryAdapter(store)
    tenant_repo = fake_adapters.FakeTenantRepository()
    tenant_repo.save(_build_tenant(professional_name="Dra. Sofia López"))

    id_gen = fake_adapters.SequenceIdGenerator([])
    clock = fake_adapters.FixedClock(_NOW)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()

    svc = gcal_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repo,
        google_calendar_provider=google_provider,
        id_generator=id_gen,
        clock=clock,
        tenant_repository=tenant_repo,
    )

    name = svc.get_professional_name("tenant-1")
    assert name == "Dra. Sofia López"


def test_get_professional_name_returns_none_without_tenant_repo() -> None:
    import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as gcal_repo
    import src.adapters.outbound.inmemory.store as in_memory_store
    import src.services.use_cases.google_calendar_onboarding_service as gcal_service

    store = in_memory_store.InMemoryStore()
    calendar_connection_repo = gcal_repo.InMemoryGoogleCalendarConnectionRepositoryAdapter(store)
    id_gen = fake_adapters.SequenceIdGenerator([])
    clock = fake_adapters.FixedClock(_NOW)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()

    svc = gcal_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repo,
        google_calendar_provider=google_provider,
        id_generator=id_gen,
        clock=clock,
    )

    name = svc.get_professional_name("tenant-1")
    assert name is None
