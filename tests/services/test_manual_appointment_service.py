import datetime

import pydantic
import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.manual_appointment_repository_adapter as manual_appointment_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.booking_constants as booking_constants
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.tenant as tenant_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.manual_appointment_dto as manual_appointment_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.manual_appointment_service as manual_appointment_service
import tests.fakes.fake_adapters as fake_adapters


def _build_event_description_builder(
    store: in_memory_store.InMemoryStore,
) -> event_description_builder_mod.EventDescriptionBuilder:
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="Eres un asistente.",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    return event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo
    )


def build_service(
    professional_name: str | None = "Test Professional",
) -> tuple[
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
    tenant_repository = fake_adapters.FakeTenantRepository()
    tenant_repository.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Tenant",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            professional_name=professional_name,
        )
    )
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["conf-req-1", "manual-appt-1"])
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
        tenant_repository=tenant_repository,
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
    builder = _build_event_description_builder(store)
    service = manual_appointment_service.ManualAppointmentService(
        manual_appointment_repository=manual_repository,
        patient_repository=patient_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        event_description_builder=builder,
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
            claims=build_claims("professional"),
            create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
                patient_whatsapp_user_id="wa-1",
                start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
                end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
                timezone="America/Bogota",
                summary=None,
                payment_amount_cop=120000,
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
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary=None,
            payment_amount_cop=120000,
        ),
    )

    assert created.appointment_id == "manual-appt-1"
    assert google_provider.created_event_summaries == ["Test Professional/Jane Doe"]
    assert google_provider.created_event_descriptions == [
        booking_constants.VIRTUAL_SESSION_EVENT_INSTRUCTIONS
    ]

    rescheduled = service.reschedule_appointment(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.RescheduleManualAppointmentDTO(
            start_at=datetime.datetime(2026, 1, 16, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 16, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita - Jane Doe reprogramada",
        ),
    )

    assert rescheduled.start_at == datetime.datetime(2026, 1, 16, 10, 0, tzinfo=datetime.UTC)
    assert google_provider.updated_event_summaries == ["Test Professional/Jane Doe"]
    assert google_provider.updated_event_descriptions == ["Cita - Jane Doe reprogramada"]
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
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita Jane",
            payment_amount_cop=120000,
        ),
    )

    cancelled = service.cancel_appointment(
        claims=build_claims("professional"),
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
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita Jane",
            payment_amount_cop=120000,
        ),
    )
    google_provider.delete_event_errors = [
        service_exceptions.ExternalProviderError("google delete failed (status=500, detail=boom)")
    ]

    with pytest.raises(service_exceptions.ExternalProviderError):
        service.cancel_appointment(
            claims=build_claims("professional"),
            appointment_id=created.appointment_id,
            input_dto=manual_appointment_dto.CancelManualAppointmentDTO(reason=None),
        )


def test_update_payment_updates_manual_scheduled_appointment() -> None:
    service, manual_repository, patient_repository, _ = build_service()
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita Jane",
            payment_amount_cop=120000,
        ),
    )

    updated = service.update_payment(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.UpdateManualAppointmentPaymentDTO(
            payment_amount_cop=120000,
            payment_method="TRANSFER",
            payment_status="PAID",
        ),
    )

    assert updated.payment_amount_cop == 120000
    assert updated.payment_method == "TRANSFER"
    assert updated.payment_status == "PAID"
    assert updated.payment_updated_at is not None
    stored = manual_repository.get_by_id("tenant-1", created.appointment_id)
    assert stored is not None
    assert stored.payment_amount_cop == 120000
    assert stored.payment_status == "PAID"


def test_update_payment_rejects_cancelled_manual_appointment() -> None:
    service, _, patient_repository, _ = build_service()
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Cita Jane",
            payment_amount_cop=120000,
        ),
    )
    service.cancel_appointment(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.CancelManualAppointmentDTO(reason="cancelada"),
    )

    with pytest.raises(service_exceptions.InvalidStateError):
        service.update_payment(
            claims=build_claims("professional"),
            appointment_id=created.appointment_id,
            input_dto=manual_appointment_dto.UpdateManualAppointmentPaymentDTO(
                payment_amount_cop=120000,
                payment_method="CASH",
                payment_status="PENDING",
            ),
        )


def test_update_manual_payment_dto_rejects_non_positive_amount() -> None:
    with pytest.raises(pydantic.ValidationError):
        manual_appointment_dto.UpdateManualAppointmentPaymentDTO(
            payment_amount_cop=0,
            payment_method="CASH",
            payment_status="PENDING",
        )


def test_create_virtual_appointment_passes_attendee_email_and_meet_flag() -> None:
    service, _, patient_repository, google_provider = build_service()
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            is_virtual=True,
            payment_amount_cop=120000,
        ),
    )

    assert google_provider.last_create_attendee_emails == [["jane@example.com"]]
    assert google_provider.last_create_with_meet == [True]
    assert created.is_virtual is True
    assert created.meet_url == "https://meet.google.com/fake-meet"


def test_create_presencial_appointment_passes_attendee_email_no_meet() -> None:
    service, _, patient_repository, google_provider = build_service()
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    created = service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            is_virtual=False,
            payment_amount_cop=120000,
        ),
    )

    assert google_provider.last_create_attendee_emails == [["jane@example.com"]]
    assert google_provider.last_create_with_meet == [False]
    assert created.is_virtual is False
    assert created.meet_url is None


def test_create_appointment_uses_professional_name_as_event_title() -> None:
    service, _, patient_repository, google_provider = build_service()
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Ansiedad",
            payment_amount_cop=120000,
        ),
    )

    assert google_provider.created_event_summaries == ["Test Professional/Jane Doe"]
    assert google_provider.created_event_descriptions == [
        booking_constants.VIRTUAL_SESSION_EVENT_INSTRUCTIONS
    ]


def test_create_appointment_falls_back_to_profesional_when_name_unavailable() -> None:
    service, _, patient_repository, google_provider = build_service(professional_name=None)
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    service.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=datetime.datetime(2026, 1, 15, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.UTC),
            timezone="America/Bogota",
            summary="Ansiedad",
            payment_amount_cop=120000,
        ),
    )

    assert google_provider.created_event_summaries == ["Profesional/Jane Doe"]
    assert google_provider.created_event_descriptions == [
        booking_constants.VIRTUAL_SESSION_EVENT_INSTRUCTIONS
    ]


# ---------------------------------------------------------------------------
# change_modality tests
# ---------------------------------------------------------------------------


def _build_service_with_eval_tenant(
    is_eval: bool,
) -> tuple[
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
    tenant_repo = fake_adapters.FakeTenantRepository()
    tenant_repo.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Tenant",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            is_eval_tenant=is_eval,
        )
    )
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(
        ["conf-req-1", "manual-appt-1", "manual-appt-2"]
    )
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
    builder = _build_event_description_builder(store)
    svc = manual_appointment_service.ManualAppointmentService(
        manual_appointment_repository=manual_repository,
        patient_repository=patient_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        event_description_builder=builder,
        tenant_repository=tenant_repo,
    )
    return svc, manual_repository, patient_repository, google_provider


def _seed_patient(
    patient_repository: patient_repository_adapter.InMemoryPatientRepositoryAdapter,
) -> None:
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )


def _create_scheduled_appointment(
    svc: manual_appointment_service.ManualAppointmentService,
    is_virtual: bool = True,
    start_at: datetime.datetime | None = None,
) -> manual_appointment_dto.ManualAppointmentDTO:
    resolved_start = start_at or datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.UTC)
    return svc.create_appointment(
        claims=build_claims("professional"),
        create_dto=manual_appointment_dto.CreateManualAppointmentDTO(
            patient_whatsapp_user_id="wa-1",
            start_at=resolved_start,
            end_at=resolved_start + datetime.timedelta(hours=1),
            timezone="America/Bogota",
            is_virtual=is_virtual,
            payment_amount_cop=120000,
        ),
    )


def test_change_modality_noop_when_same_modality_manual() -> None:
    """Requesting the same modality returns DTO without calling Calendar."""
    service, _manual_repository, patient_repository, google_provider = build_service()
    _seed_patient(patient_repository)
    created = _create_scheduled_appointment(service, is_virtual=True)

    result = service.change_modality(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
            new_modality="VIRTUAL"
        ),
    )

    assert result.is_virtual is True
    # No additional Calendar calls beyond create_event
    assert len(google_provider.updated_events) == 0


def test_change_modality_blocks_past_appointment_manual() -> None:
    """Past appointments (start_at <= now) raise InvalidStateError."""
    service, _manual_repository, patient_repository, google_provider = build_service()
    _seed_patient(patient_repository)
    past_start = datetime.datetime(2026, 1, 5, 10, 0, tzinfo=datetime.UTC)
    created = _create_scheduled_appointment(service, is_virtual=True, start_at=past_start)

    with pytest.raises(service_exceptions.InvalidStateError) as exc_info:
        service.change_modality(
            claims=build_claims("professional"),
            appointment_id=created.appointment_id,
            input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
                new_modality="PRESENCIAL"
            ),
        )

    assert "past" in str(exc_info.value).lower()
    assert len(google_provider.updated_events) == 0


def test_change_modality_raises_not_found_for_missing_appointment() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.change_modality(
            claims=build_claims("professional"),
            appointment_id="does-not-exist",
            input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
                new_modality="VIRTUAL"
            ),
        )


def test_change_modality_virtual_to_presencial_updates_calendar_manual() -> None:
    """VIRTUAL → PRESENCIAL: update_event called with with_meet=False; is_virtual persisted."""
    service, manual_repository, patient_repository, google_provider = build_service()
    _seed_patient(patient_repository)
    created = _create_scheduled_appointment(service, is_virtual=True)

    result = service.change_modality(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
            new_modality="PRESENCIAL"
        ),
    )

    assert result.is_virtual is False
    assert len(google_provider.updated_events) == 1
    assert google_provider.last_update_with_meet == [False]
    reloaded = manual_repository.get_by_id("tenant-1", created.appointment_id)
    assert reloaded is not None
    assert reloaded.is_virtual is False


def test_change_modality_presencial_to_virtual_updates_calendar_manual() -> None:
    """PRESENCIAL → VIRTUAL: update_event called with with_meet=True; meet_url set."""
    service, manual_repository, patient_repository, google_provider = build_service()
    _seed_patient(patient_repository)
    created = _create_scheduled_appointment(service, is_virtual=False)

    result = service.change_modality(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
            new_modality="VIRTUAL"
        ),
    )

    assert result.is_virtual is True
    assert result.meet_url == "https://meet.google.com/fake-meet"
    assert len(google_provider.updated_events) == 1
    assert google_provider.last_update_with_meet == [True]
    reloaded = manual_repository.get_by_id("tenant-1", created.appointment_id)
    assert reloaded is not None
    assert reloaded.is_virtual is True
    assert reloaded.meet_url == "https://meet.google.com/fake-meet"


def test_change_modality_skips_calendar_for_eval_tenant_manual() -> None:
    """Eval tenant: is_virtual flipped in DB, no Calendar call."""
    service, manual_repository, patient_repository, google_provider = (
        _build_service_with_eval_tenant(is_eval=True)
    )
    _seed_patient(patient_repository)
    created = _create_scheduled_appointment(service, is_virtual=True)

    result = service.change_modality(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
            new_modality="PRESENCIAL"
        ),
    )

    assert result.is_virtual is False
    # No update_event calls (only the original create_event from create_appointment)
    assert len(google_provider.updated_events) == 0
    reloaded = manual_repository.get_by_id("tenant-1", created.appointment_id)
    assert reloaded is not None
    assert reloaded.is_virtual is False


def test_change_modality_blocks_cancelled_appointment() -> None:
    """Cancelled appointments raise InvalidStateError."""
    service, _manual_repository, patient_repository, _google_provider = build_service()
    _seed_patient(patient_repository)
    created = _create_scheduled_appointment(service, is_virtual=True)
    service.cancel_appointment(
        claims=build_claims("professional"),
        appointment_id=created.appointment_id,
        input_dto=manual_appointment_dto.CancelManualAppointmentDTO(reason=None),
    )

    with pytest.raises(service_exceptions.InvalidStateError):
        service.change_modality(
            claims=build_claims("professional"),
            appointment_id=created.appointment_id,
            input_dto=manual_appointment_dto.ChangeManualAppointmentModalityInputDTO(
                new_modality="PRESENCIAL"
            ),
        )
