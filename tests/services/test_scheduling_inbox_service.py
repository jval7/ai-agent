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


def test_submit_professional_slots_rejects_off_grid_duration() -> None:
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
                        end_at=datetime.datetime(2026, 1, 1, 10, 25, tzinfo=datetime.UTC),
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
# Slot duration preset validation (per-appointment, picked by professional)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("duration_minutes", [15, 30, 45, 60, 90, 120])  # type: ignore[misc, unused-ignore]
def test_submit_professional_slots_accepts_any_preset_duration(duration_minutes: int) -> None:
    service, _, _, _ = build_services()
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


# ---------------------------------------------------------------------------
# Fix B2: payment fallback message reads AgentProfile.payment_methods
# ---------------------------------------------------------------------------


def _build_inbox_service_with_payment_methods(
    payment_methods: list[agent_profile_entity.PaymentMethod],
) -> scheduling_inbox_service.SchedulingInboxService:
    """Build an inbox service whose AgentProfile has the given payment_methods."""
    store = in_memory_store.InMemoryStore()
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="Eres un asistente.",
            payment_methods=payment_methods,
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
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
    id_generator = fake_adapters.SequenceIdGenerator(["msg-b2-1"])
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    task_sched = inmemory_task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo,
    )
    core_svc = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
    )
    return scheduling_inbox_service.SchedulingInboxService(
        scheduling_repository=scheduling_repository,
        scheduling_service=core_svc,
        google_calendar_onboarding_service=google_service,
        conversation_repository=conversation_repository,
        whatsapp_connection_repository=whatsapp_connection_repository,
        whatsapp_provider=fake_adapters.FakeWhatsappProvider(),
        id_generator=id_generator,
        clock=clock,
        agent_profile_repository=agent_profile_repo,
    )


def test_payment_pending_fallback_does_not_contain_nequi_when_zelle_configured() -> None:
    """Fix B2: fallback message must not contain 'Nequi' when only Zelle is configured."""
    svc = _build_inbox_service_with_payment_methods(
        [
            agent_profile_entity.PaymentMethod(
                currency="USD",
                method_name="Zelle",
                holder="Test Professional",
                instructions="test@example.com",
                applies_when="International patients",
            )
        ]
    )
    message = svc._build_payment_pending_fallback("tenant-1")

    assert "Nequi" not in message
    assert "318 732 6409" not in message
    assert "Zelle" in message


def test_payment_pending_fallback_is_generic_when_no_payment_methods() -> None:
    """Fix B2: fallback must be generic (no account numbers) when payment_methods is empty."""
    svc = _build_inbox_service_with_payment_methods([])
    message = svc._build_payment_pending_fallback("tenant-1")

    assert "318 732 6409" not in message
    assert "Nequi" not in message
    # Must not contain any phone-number-like sequence
    assert "318" not in message


@pytest.mark.parametrize("duration_minutes", [10, 25, 50, 75, 100, 150])  # type: ignore[misc, unused-ignore]
def test_submit_professional_slots_rejects_non_preset_duration(duration_minutes: int) -> None:
    service, _, _, _ = build_services()
    end_at = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC) + datetime.timedelta(
        minutes=duration_minutes
    )
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
                        end_at=end_at,
                        timezone="America/Bogota",
                    )
                ],
                professional_note=None,
            ),
        )


# ---------------------------------------------------------------------------
# resolve_consultation_review (REQUEST_MORE_INFO / REJECT)
# ---------------------------------------------------------------------------


def test_resolve_consultation_review_request_more_info_sends_followup() -> None:
    service, repository, whatsapp_provider, _ = build_services()

    response = service.resolve_consultation_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="REQUEST_MORE_INFO",
            professional_note="dame mas detalle del motivo",
        ),
    )

    assert response.status == "AWAITING_CONSULTATION_DETAILS"
    assert "motivo de consulta" in response.assistant_text.lower()
    assert len(whatsapp_provider.sent_messages) == 1
    assert whatsapp_provider.sent_messages[0]["text"] == response.assistant_text
    saved = repository.get_request_by_id("tenant-1", "req-1")
    assert saved is not None
    assert saved.status == "AWAITING_CONSULTATION_DETAILS"


def test_resolve_consultation_review_reject_closes_request() -> None:
    service, repository, whatsapp_provider, _ = build_services()

    response = service.resolve_consultation_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="REJECT",
            professional_note="fuera de mi especialidad",
        ),
    )

    assert response.status == "CONSULTATION_REJECTED"
    assert "no puedo ayudarte" in response.assistant_text.lower()
    assert len(whatsapp_provider.sent_messages) == 1
    saved = repository.get_request_by_id("tenant-1", "req-1")
    assert saved is not None
    assert saved.status == "CONSULTATION_REJECTED"


def test_resolve_consultation_review_requires_professional_role() -> None:
    service, _, whatsapp_provider, _ = build_services()
    non_professional_claims = auth_dto.TokenClaimsDTO(
        sub="user-2",
        tenant_id="tenant-1",
        role="member",
        exp=0,
        jti="jti-2",
        token_kind="access",
    )

    with pytest.raises(service_exceptions.AuthorizationError):
        service.resolve_consultation_review(
            claims=non_professional_claims,
            conversation_id="conv-1",
            request_id="req-1",
            input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
                decision="REQUEST_MORE_INFO",
                professional_note="dame mas detalle",
            ),
        )

    assert whatsapp_provider.sent_messages == []


def test_resolve_consultation_review_raises_when_conversation_missing() -> None:
    service, repository, _, _ = build_services()
    # Build an orphan request whose conversation_id is not in the conversation repo.
    repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-orphan",
            tenant_id="tenant-1",
            conversation_id="conv-orphan",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=1,
            patient_preference_note=None,
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

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.resolve_consultation_review(
            claims=build_claims(),
            conversation_id="conv-orphan",
            request_id="req-orphan",
            input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
                decision="REQUEST_MORE_INFO",
                professional_note="dame mas detalle",
            ),
        )


# ---------------------------------------------------------------------------
# resolve_payment_review (APPROVE / SEND_REMINDER)
# ---------------------------------------------------------------------------


def _seed_payment_pending_request(
    repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    *,
    request_id: str = "req-pay-1",
) -> None:
    repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id=request_id,
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PAYMENT_CONFIRMATION",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            payment_amount_cop=None,
            payment_status="PENDING",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )


def test_resolve_payment_review_approve_marks_paid_and_sends_followup() -> None:
    service, repository, whatsapp_provider, _ = build_services()
    _seed_payment_pending_request(repository)

    response = service.resolve_payment_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-pay-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            professional_note=None,
            payment_amount_cop=80000,
            payment_currency="COP",
        ),
    )

    assert response.status == "AWAITING_PATIENT_CHOICE"
    assert "Pago recibido" in response.assistant_text
    assert len(whatsapp_provider.sent_messages) == 1
    saved = repository.get_request_by_id("tenant-1", "req-pay-1")
    assert saved is not None
    assert saved.status == "AWAITING_PATIENT_CHOICE"
    assert saved.payment_status == "PAID"
    assert saved.payment_amount_cop == 80000


def test_resolve_payment_review_send_reminder_keeps_request_pending() -> None:
    service, repository, whatsapp_provider, _ = build_services()
    _seed_payment_pending_request(repository)

    response = service.resolve_payment_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-pay-1",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="SEND_REMINDER",
            professional_note=None,
        ),
    )

    assert response.status == "AWAITING_PAYMENT_CONFIRMATION"
    assert "completar el pago" in response.assistant_text
    assert len(whatsapp_provider.sent_messages) == 1
    saved = repository.get_request_by_id("tenant-1", "req-pay-1")
    assert saved is not None
    assert saved.status == "AWAITING_PAYMENT_CONFIRMATION"
    assert saved.payment_status == "PENDING"


def test_resolve_payment_review_requires_professional_role() -> None:
    service, repository, whatsapp_provider, _ = build_services()
    _seed_payment_pending_request(repository)
    non_professional_claims = auth_dto.TokenClaimsDTO(
        sub="user-2",
        tenant_id="tenant-1",
        role="member",
        exp=0,
        jti="jti-2",
        token_kind="access",
    )

    with pytest.raises(service_exceptions.AuthorizationError):
        service.resolve_payment_review(
            claims=non_professional_claims,
            conversation_id="conv-1",
            request_id="req-pay-1",
            input_dto=scheduling_dto.PaymentReviewDecisionDTO(
                decision="SEND_REMINDER",
                professional_note=None,
            ),
        )

    assert whatsapp_provider.sent_messages == []


# ---------------------------------------------------------------------------
# LLM-generated review messages (consultation + payment)
# ---------------------------------------------------------------------------


def _build_inbox_service_with_llm(
    llm_provider: fake_adapters.FakeLlmProvider,
) -> tuple[
    scheduling_inbox_service.SchedulingInboxService,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    fake_adapters.FakeWhatsappProvider,
]:
    """Like build_services() but wires an llm_provider so the LLM helpers run."""
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
        llm_provider=llm_provider,
        agent_profile_repository=agent_profile_repo,
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
    return inbox_service, scheduling_repository, whatsapp_provider


def test_resolve_consultation_review_uses_llm_message_when_available() -> None:
    llm = fake_adapters.FakeLlmProvider(reply_content="Mensaje generado por LLM 🎯")
    service, _, whatsapp_provider = _build_inbox_service_with_llm(llm)

    response = service.resolve_consultation_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="REQUEST_MORE_INFO",
            professional_note="dame mas detalle del motivo",
        ),
    )

    assert response.assistant_text == "Mensaje generado por LLM 🎯"
    assert whatsapp_provider.sent_messages[0]["text"] == "Mensaje generado por LLM 🎯"
    assert len(llm.calls) == 1


def test_resolve_consultation_review_falls_back_when_llm_returns_blank() -> None:
    llm = fake_adapters.FakeLlmProvider(reply_content="   \n")
    service, _, whatsapp_provider = _build_inbox_service_with_llm(llm)

    response = service.resolve_consultation_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="REQUEST_MORE_INFO",
            professional_note="dame mas detalle",
        ),
    )

    assert "motivo de consulta" in response.assistant_text.lower()
    assert whatsapp_provider.sent_messages[0]["text"] == response.assistant_text


def test_resolve_consultation_review_falls_back_when_llm_raises() -> None:
    llm = fake_adapters.FakeLlmProvider(reply_content="should not be used")
    llm.queued_errors.append(service_exceptions.ExternalProviderError("simulated llm failure"))
    service, _, whatsapp_provider = _build_inbox_service_with_llm(llm)

    response = service.resolve_consultation_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-1",
        input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
            decision="REJECT",
            professional_note="fuera de mi especialidad",
        ),
    )

    assert "no puedo ayudarte" in response.assistant_text.lower()
    assert whatsapp_provider.sent_messages[0]["text"] == response.assistant_text


def _seed_payment_pending_in_llm_setup(
    repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
) -> None:
    repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-pay-llm",
            tenant_id="tenant-1",
            conversation_id="conv-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PAYMENT_CONFIRMATION",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            payment_amount_cop=None,
            payment_status="PENDING",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )


def test_resolve_payment_review_uses_llm_message_when_available() -> None:
    llm = fake_adapters.FakeLlmProvider(reply_content="Pago confirmado, mensaje LLM ✨")
    service, repository, whatsapp_provider = _build_inbox_service_with_llm(llm)
    _seed_payment_pending_in_llm_setup(repository)

    response = service.resolve_payment_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-pay-llm",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="APPROVE",
            professional_note=None,
            payment_amount_cop=80000,
            payment_currency="COP",
        ),
    )

    assert response.assistant_text == "Pago confirmado, mensaje LLM ✨"
    assert whatsapp_provider.sent_messages[0]["text"] == "Pago confirmado, mensaje LLM ✨"
    assert len(llm.calls) == 1


def test_resolve_payment_review_falls_back_when_llm_raises() -> None:
    llm = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm.queued_errors.append(service_exceptions.ExternalProviderError("simulated llm failure"))
    service, repository, whatsapp_provider = _build_inbox_service_with_llm(llm)
    _seed_payment_pending_in_llm_setup(repository)

    response = service.resolve_payment_review(
        claims=build_claims(),
        conversation_id="conv-1",
        request_id="req-pay-llm",
        input_dto=scheduling_dto.PaymentReviewDecisionDTO(
            decision="SEND_REMINDER",
            professional_note=None,
        ),
    )

    assert "completar el pago" in response.assistant_text
    assert whatsapp_provider.sent_messages[0]["text"] == response.assistant_text


def test_resolve_consultation_review_raises_when_connection_missing_credentials() -> None:
    service, _, _, _ = build_services()
    # Save replaces the existing connection by tenant_id (port semantics).
    service._whatsapp_connection_repository.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token=None,
            status="PENDING",
            embedded_signup_state=None,
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    with pytest.raises(service_exceptions.InvalidStateError):
        service.resolve_consultation_review(
            claims=build_claims(),
            conversation_id="conv-1",
            request_id="req-1",
            input_dto=scheduling_dto.ConsultationReviewDecisionDTO(
                decision="REQUEST_MORE_INFO",
                professional_note="dame mas detalle",
            ),
        )
