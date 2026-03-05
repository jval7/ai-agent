import datetime

import pytest

import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.manual_appointment_repository_adapter as manual_appointment_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.patient as patient_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.manual_appointment_dto as manual_appointment_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.manual_appointment_service as manual_appointment_service
import tests.fakes.fake_adapters as fake_adapters


def build_service() -> tuple[
    manual_appointment_service.ManualAppointmentService,
    manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter,
    patient_repository_adapter.InMemoryPatientRepositoryAdapter,
    fake_adapters.FakeGoogleCalendarProvider,
]:
    store = in_memory_store.InMemoryStore()
    manual_repository = (
        manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter(store)
    )
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["manual-appt-1"])
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
    service = manual_appointment_service.ManualAppointmentService(
        manual_appointment_repository=manual_repository,
        patient_repository=patient_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )
    return service, manual_repository, patient_repository, google_provider


def build_claims(role: str) -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id="tenant-1",
        role=role,
        exp=2000000000,
        jti="jti-1",
        token_kind="access",
    )


def test_create_manual_appointment_requires_existing_patient() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.create_appointment(
            claims=build_claims("owner"),
            create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
                patient_whatsapp_user_id="wa-1",
                start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
                end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
                timezone="America/Bogota",
                summary=None,
            ),
        )


def test_create_and_reschedule_manual_appointment() -> None:
    service, manual_repository, patient_repository, google_provider = build_service()
    patient_repository.save(
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

    created = service.create_appointment(
        claims=build_claims("owner"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary=None,
        ),
    )

    assert created.appointment_id == "manual-appt-1"
    assert google_provider.created_event_summaries == ["Cita - Jane Doe"]

    rescheduled = service.reschedule_appointment(
        claims=build_claims("owner"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.RescheduleManualAppointmentDTO(
            start_at=datetime.datetime(2026, 1, 16, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 16, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita - Jane Doe reprogramada",
        ),
    )

    assert rescheduled.start_at == datetime.datetime(2026, 1, 16, 10, 0, tzinfo=datetime.UTC)
    assert google_provider.updated_event_summaries == ["Cita - Jane Doe reprogramada"]
    stored = manual_repository.get_by_id("tenant-1", "manual-appt-1")
    assert stored is not None
    assert stored.status == "SCHEDULED"


def test_cancel_manual_appointment_marks_cancelled() -> None:
    service, manual_repository, patient_repository, google_provider = build_service()
    patient_repository.save(
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
    created = service.create_appointment(
        claims=build_claims("owner"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita Jane",
        ),
    )

    cancelled = service.cancel_appointment(
        claims=build_claims("owner"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.CancelManualAppointmentDTO(reason="Paciente cancela"),
    )

    assert cancelled.status == "CANCELLED"
    assert cancelled.calendar_event_id is None
    assert google_provider.deleted_event_ids == ["event-1"]
    stored = manual_repository.get_by_id("tenant-1", "manual-appt-1")
    assert stored is not None
    assert stored.cancelled_at is not None


def test_cancel_manual_appointment_keeps_consistency_on_google_error() -> None:
    service, _, patient_repository, google_provider = build_service()
    patient_repository.save(
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
    created = service.create_appointment(
        claims=build_claims("owner"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita Jane",
        ),
    )
    google_provider.delete_event_errors = [
        service_exceptions.ExternalProviderError("google delete failed (status=500, detail=boom)")
    ]

    with pytest.raises(service_exceptions.ExternalProviderError):
        service.cancel_appointment(
            claims=build_claims("owner"),
            appointment_id=created.appointment_id,
            input_dto=manual_appointment_dto.CancelManualAppointmentDTO(reason=None),
        )
