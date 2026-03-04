import datetime
import pathlib
import tempfile

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.refresh_token_repository_adapter as refresh_token_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
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
    refresh_token_repository = (
        refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter()
    )
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
        refresh_token_repository=refresh_token_repository,
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


def test_calendar_and_scheduling_state_persist_across_restart() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot_path = str(pathlib.Path(temp_dir) / "memory_store.json")
        now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

        first_store = in_memory_store.InMemoryStore(persistence_file_path=snapshot_path)
        first_calendar_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
            first_store
        )
        first_scheduling_repository = (
            scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(first_store)
        )
        first_patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(
            first_store
        )

        first_calendar_repository.save(
            google_calendar_connection_entity.GoogleCalendarConnection(
                tenant_id="tenant-1",
                professional_user_id="user-1",
                status="CONNECTED",
                calendar_id="primary",
                timezone="America/Bogota",
                access_token="access-1",
                refresh_token="refresh-1",
                token_expires_at=now_value + datetime.timedelta(hours=1),
                oauth_state=None,
                scope="calendar",
                updated_at=now_value,
                connected_at=now_value,
            )
        )
        first_scheduling_repository.save_request(
            scheduling_request_entity.SchedulingRequest(
                id="req-1",
                tenant_id="tenant-1",
                conversation_id="conv-1",
                whatsapp_user_id="wa-user-1",
                request_kind="INITIAL",
                status="AWAITING_PATIENT_CHOICE",
                round_number=1,
                patient_preference_note="prefiere tarde",
                rejection_summary=None,
                professional_note=None,
                slots=[
                    scheduling_slot_entity.SchedulingSlot(
                        id="slot-1",
                        start_at=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
                        end_at=datetime.datetime(2026, 1, 2, 11, 0, tzinfo=datetime.UTC),
                        timezone="America/Bogota",
                        status="PROPOSED",
                    )
                ],
                slot_options_map={"1": "slot-1"},
                selected_slot_id=None,
                calendar_event_id=None,
                created_at=now_value,
                updated_at=now_value,
            )
        )
        first_patient_repository.save(
            patient_entity.Patient(
                tenant_id="tenant-1",
                whatsapp_user_id="wa-user-1",
                first_name="Jane",
                last_name="Doe",
                email="jane@example.com",
                age=29,
                consultation_reason="Ansiedad",
                location="Bogota",
                phone="573001112233",
                created_at=now_value,
            )
        )

        second_store = in_memory_store.InMemoryStore(persistence_file_path=snapshot_path)
        second_calendar_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
            second_store
        )
        second_scheduling_repository = (
            scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(second_store)
        )
        second_patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(
            second_store
        )

        restored_connection = second_calendar_repository.get_by_tenant_id("tenant-1")
        restored_request = second_scheduling_repository.get_request_by_id("tenant-1", "req-1")
        restored_patient = second_patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1")

        assert restored_connection is not None
        assert restored_connection.status == "CONNECTED"
        assert restored_connection.calendar_id == "primary"
        assert restored_connection.timezone == "America/Bogota"
        assert restored_request is not None
        assert restored_request.status == "AWAITING_PATIENT_CHOICE"
        assert len(restored_request.slots) == 1
        assert restored_request.slots[0].id == "slot-1"
        assert restored_patient is not None
        assert restored_patient.first_name == "Jane"
