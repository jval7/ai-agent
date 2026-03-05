import datetime

import pytest

import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.patient_query_service as patient_query_service
import tests.fakes.fake_adapters as fake_adapters


def build_service() -> tuple[
    patient_query_service.PatientQueryService,
    patient_repository_adapter.InMemoryPatientRepositoryAdapter,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
]:
    store = in_memory_store.InMemoryStore()
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["oauth-state-1"])
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    calendar_connection_repository.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="access-1",
            refresh_token="refresh-1",
            token_expires_at=datetime.datetime(2026, 1, 11, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC),
            connected_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    google_provider.refreshed_tokens_by_refresh_token["refresh-1"] = (
        google_calendar_dto.GoogleOauthTokensDTO(
            access_token="access-2",
            refresh_token="refresh-1",
            expires_in_seconds=3600,
            scope="calendar",
            token_type="Bearer",
        )
    )
    service = patient_query_service.PatientQueryService(
        patient_repository=patient_repository,
        scheduling_repository=scheduling_repository,
        google_calendar_onboarding_service=google_service,
        clock=clock,
    )
    return service, patient_repository, scheduling_repository, google_provider


def build_claims(role: str) -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id="tenant-1",
        role=role,
        exp=2000000000,
        jti="jti-1",
        token_kind="access",
    )


def test_list_patients_requires_owner_role() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(service_exceptions.AuthorizationError):
        service.list_patients(build_claims("agent"))


def test_get_patient_raises_not_found() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.get_patient(build_claims("owner"), "wa-404")


def test_list_patients_returns_sorted_items() -> None:
    service, repository, _, _ = build_service()
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            consultation_reason="Ansiedad",
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-2",
            first_name="John",
            last_name="Smith",
            email="john@example.com",
            age=34,
            consultation_reason="Sueno",
            location="Medellin",
            phone="573001445566",
            created_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC),
        )
    )

    response = service.list_patients(build_claims("owner"))

    assert len(response.items) == 2
    assert response.items[0].whatsapp_user_id == "wa-2"
    assert response.items[1].whatsapp_user_id == "wa-1"


def test_get_patient_returns_single_patient() -> None:
    service, repository, _, _ = build_service()
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            consultation_reason="Ansiedad",
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    response = service.get_patient(build_claims("owner"), "wa-1")

    assert response.whatsapp_user_id == "wa-1"
    assert response.first_name == "Jane"


def test_delete_patient_requires_owner_role() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(service_exceptions.AuthorizationError):
        service.delete_patient(build_claims("agent"), "wa-1")


def test_delete_patient_removes_patient_for_tenant() -> None:
    service, repository, scheduling_repository, google_provider = build_service()
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            consultation_reason="Ansiedad",
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-2",
            whatsapp_user_id="wa-1",
            first_name="John",
            last_name="Smith",
            email="john@example.com",
            age=34,
            consultation_reason="Insomnio",
            location="Medellin",
            phone="573001445566",
            created_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC),
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-booked-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-1",
            request_kind="INITIAL",
            status="BOOKED",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id="slot-1",
            calendar_event_id="evt-1",
            created_at=datetime.datetime(2026, 1, 3, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 3, tzinfo=datetime.UTC),
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-booked-2",
            tenant_id="tenant-1",
            conversation_id="conv-2",
            whatsapp_user_id="wa-2",
            request_kind="INITIAL",
            status="BOOKED",
            round_number=1,
            patient_preference_note="prefiere mañana",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id="slot-2",
            calendar_event_id="evt-2",
            created_at=datetime.datetime(2026, 1, 4, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 4, tzinfo=datetime.UTC),
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-progress-1",
            tenant_id="tenant-1",
            conversation_id="conv-3",
            whatsapp_user_id="wa-1",
            request_kind="INITIAL",
            status="COLLECTING_PREFERENCES",
            round_number=1,
            patient_preference_note="prefiere virtual",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=datetime.datetime(2026, 1, 5, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 5, tzinfo=datetime.UTC),
        )
    )

    service.delete_patient(build_claims("owner"), "wa-1")

    assert repository.get_by_whatsapp_user("tenant-1", "wa-1") is None
    assert repository.get_by_whatsapp_user("tenant-2", "wa-1") is not None
    assert google_provider.deleted_event_ids == ["evt-1"]
    deleted_patient_request = scheduling_repository.get_request_by_id("tenant-1", "req-booked-1")
    deleted_patient_pending_request = scheduling_repository.get_request_by_id(
        "tenant-1", "req-progress-1"
    )
    unaffected_request = scheduling_repository.get_request_by_id("tenant-1", "req-booked-2")
    assert deleted_patient_request is None
    assert deleted_patient_pending_request is None
    assert unaffected_request is not None
    assert unaffected_request.status == "BOOKED"
    assert unaffected_request.professional_note is None
    assert unaffected_request.calendar_event_id == "evt-2"
