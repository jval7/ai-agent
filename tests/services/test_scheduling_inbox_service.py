import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as inmemory_task_scheduler_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.dto.auth_dto as auth_dto
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_inbox_service as scheduling_inbox_service
import src.services.use_cases.scheduling_service as scheduling_service
import tests.fakes.fake_adapters as fake_adapters


def build_claims() -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id="tenant-1",
        role="professional",
        exp=0,
        jti="jti-1",
        token_kind="access",
    )


def build_services() -> tuple[
    scheduling_inbox_service.SchedulingInboxService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeWhatsappProvider,
    fake_adapters.FakeGoogleCalendarProvider,
]:
    store = in_memory_store.InMemoryStore()
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    whatsapp_connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    id_generator = fake_adapters.SequenceIdGenerator(["msg-1", "msg-2", "msg-3"])
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    task_sched = inmemory_task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
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
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo,
    )
    scheduling_core_service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
    )
    inbox_service = scheduling_inbox_service.SchedulingInboxService(
        scheduling_repository=scheduling_repository,
        scheduling_service=scheduling_core_service,
        google_calendar_onboarding_service=google_service,
        conversation_repository=conversation_repository,
        whatsapp_connection_repository=whatsapp_connection_repository,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
    )

    conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
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
    calendar_connection_repository.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="access-1",
            refresh_token="refresh-1",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            connected_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    return inbox_service, scheduling_repository, whatsapp_provider, google_provider


def test_submit_professional_slots_resumes_conversation() -> None:
    service, repository, whatsapp_provider, _ = build_services()
    response = service.submit_professional_slots(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
            slots=[
                scheduling_dto.ProfessionalSlotInputDTO(
                    slot_id="slot-1",
                    start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                )
            ],
            professional_note="elige uno",
        ),
    )

    assert response.status == "AWAITING_PATIENT_CHOICE"
    assert len(whatsapp_provider.sent_messages) == 1
    assert "de enero a las" in whatsapp_provider.sent_messages[0]["text"]
    assert "hora Colombia" in whatsapp_provider.sent_messages[0]["text"]
    assert "T10:00:00" not in whatsapp_provider.sent_messages[0]["text"]
    saved = repository.get_request_by_id("tenant-1", "req-1")
    assert saved is not None
    assert saved.status == "AWAITING_PATIENT_CHOICE"
    assert len(saved.slots) == 1
    assert saved.slot_options_map == {"1": "slot-1"}


def test_submit_professional_slots_rejects_non_60_min_slots() -> None:
    service, _, _, _ = build_services()

    with pytest.raises(service_exceptions.InvalidStateError):
        service.submit_professional_slots(
            claims=build_claims(),
            conversation_id="conv-1",
            request_id="req-1",
            submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
                slots=[
                    scheduling_dto.ProfessionalSlotInputDTO(
                        slot_id="slot-1",
                        start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                        end_at=datetime.datetime(2026, 1, 1, 10, 30, tzinfo=datetime.UTC),
                        timezone="America/Bogota",
                    )
                ],
                professional_note=None,
            ),
        )


def test_submit_professional_slots_skips_conflicts_and_requires_remaining_slots() -> None:
    service, _, _, google_provider = build_services()
    google_provider.busy_intervals = [
        google_calendar_dto.GoogleCalendarBusyIntervalDTO(
            start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
            end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
        )
    ]

    with pytest.raises(service_exceptions.InvalidStateError):
        service.submit_professional_slots(
            claims=build_claims(),
            conversation_id="conv-1",
            request_id="req-1",
            submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
                slots=[
                    scheduling_dto.ProfessionalSlotInputDTO(
                        slot_id="slot-1",
                        start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                        end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
                        timezone="America/Bogota",
                    )
                ],
                professional_note=None,
            ),
        )


def test_submit_professional_slots_requires_professional_role() -> None:
    service, _, _, _ = build_services()
    non_owner_claims = auth_dto.TokenClaimsDTO(
        sub="user-2",
        tenant_id="tenant-1",
        role="member",
        exp=0,
        jti="jti-2",
        token_kind="access",
    )

    with pytest.raises(service_exceptions.AuthorizationError):
        service.submit_professional_slots(
            claims=non_owner_claims,
            conversation_id="conv-1",
            request_id="req-1",
            submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
                slots=[
                    scheduling_dto.ProfessionalSlotInputDTO(
                        slot_id="slot-1",
                        start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                        end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
                        timezone="America/Bogota",
                    )
                ],
                professional_note=None,
            ),
        )


# ---------------------------------------------------------------------------
# Helpers for session_duration_minutes tests
# ---------------------------------------------------------------------------

_BASE_CREATED_AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def build_services_with_duration(
    session_duration_minutes: int,
) -> tuple[
    scheduling_inbox_service.SchedulingInboxService,
    fake_adapters.FakeTenantRepository,
]:
    store = in_memory_store.InMemoryStore()
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    whatsapp_connection_repo = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    calendar_connection_repo = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )
    clock = fake_adapters.FixedClock(_BASE_CREATED_AT)
    id_generator = fake_adapters.SequenceIdGenerator(["msg-1", "msg-2", "msg-3"])
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repo,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    task_sched = inmemory_task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="Eres un asistente.",
            updated_at=_BASE_CREATED_AT,
        )
    )
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo,
    )
    scheduling_core_service = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
    )
    tenant_repo = fake_adapters.FakeTenantRepository()
    tenant_repo.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Clinic",
            created_at=_BASE_CREATED_AT,
            updated_at=_BASE_CREATED_AT,
            session_duration_minutes=session_duration_minutes,
        )
    )
    inbox_service = scheduling_inbox_service.SchedulingInboxService(
        scheduling_repository=scheduling_repo,
        scheduling_service=scheduling_core_service,
        google_calendar_onboarding_service=google_service,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=whatsapp_connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        tenant_repository=tenant_repo,
    )

    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=_BASE_CREATED_AT,
            updated_at=_BASE_CREATED_AT,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    whatsapp_connection_repo.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=_BASE_CREATED_AT,
        )
    )
    calendar_connection_repo.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="access-1",
            refresh_token="refresh-1",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=_BASE_CREATED_AT,
            connected_at=_BASE_CREATED_AT,
        )
    )
    scheduling_repo.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=_BASE_CREATED_AT,
            updated_at=_BASE_CREATED_AT,
        )
    )
    return inbox_service, tenant_repo


@pytest.mark.parametrize("duration_minutes", [30, 45, 90])  # type: ignore[misc, unused-ignore]
def test_submit_professional_slots_accepts_configured_duration(duration_minutes: int) -> None:
    service, _ = build_services_with_duration(duration_minutes)
    end_at = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC) + datetime.timedelta(
        minutes=duration_minutes
    )
    response = service.submit_professional_slots(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
            slots=[
                scheduling_dto.ProfessionalSlotInputDTO(
                    slot_id="slot-1",
                    start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                    end_at=end_at,
                    timezone="America/Bogota",
                )
            ],
            professional_note=None,
        ),
    )

    assert response.status == "AWAITING_PATIENT_CHOICE"


@pytest.mark.parametrize("duration_minutes", [30, 45, 60, 90])  # type: ignore[misc, unused-ignore]
def test_submit_professional_slots_rejects_wrong_duration_for_tenant(
    duration_minutes: int,
) -> None:
    service, _ = build_services_with_duration(duration_minutes)
    # Submit a slot that is 15 minutes (never a valid configured duration in this test)
    with pytest.raises(service_exceptions.InvalidStateError):
        service.submit_professional_slots(
            claims=build_claims(),
            conversation_id="conv-1",
            request_id="req-1",
            submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
                slots=[
                    scheduling_dto.ProfessionalSlotInputDTO(
                        slot_id="slot-1",
                        start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                        end_at=datetime.datetime(2026, 1, 1, 10, 15, tzinfo=datetime.UTC),
                        timezone="America/Bogota",
                    )
                ],
                professional_note=None,
            ),
        )


def test_submit_professional_slots_uses_60_min_default_without_tenant_repo() -> None:
    """When no tenant_repository is wired, the validator defaults to 60-minute slots."""
    service, _, _, _ = build_services()  # no tenant_repository injected

    response = service.submit_professional_slots(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        submit_dto=scheduling_dto.ProfessionalSubmitSlotsDTO(
            slots=[
                scheduling_dto.ProfessionalSlotInputDTO(
                    slot_id="slot-1",
                    start_at=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                )
            ],
            professional_note=None,
        ),
    )

    assert response.status == "AWAITING_PATIENT_CHOICE"
