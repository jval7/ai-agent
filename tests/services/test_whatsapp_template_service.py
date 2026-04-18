import datetime

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.scheduled_reminder_repository_adapter as scheduled_reminder_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.official_reminder_templates as official_reminder_templates
import src.services.exceptions as service_exceptions
import src.services.use_cases.reminder_service as reminder_service_module
import src.services.use_cases.whatsapp_template_service as whatsapp_template_service_module
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_APPOINTMENT_FAR = datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC)


def _build_context() -> tuple[
    whatsapp_template_service_module.WhatsappTemplateService,
    reminder_service_module.ReminderService,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
    whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
    scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter,
    fake_adapters.FakeWhatsappProvider,
]:
    store = in_memory_store.InMemoryStore()
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    wa_connection_repo = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    reminder_repo = (
        scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter()
    )
    task_sched = task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    wa_provider = fake_adapters.FakeWhatsappProvider()
    clock = fake_adapters.FixedClock(_NOW)
    id_gen = fake_adapters.SequenceIdGenerator(["rem-1", "rem-2", "rem-3"])

    # Seed a CONNECTED WhatsApp connection.
    wa_connection_repo.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="waba-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=_NOW,
        )
    )

    reminder_svc = reminder_service_module.ReminderService(
        scheduled_reminder_repository=reminder_repo,
        agent_profile_repository=agent_profile_repo,
        whatsapp_connection_repository=wa_connection_repo,
        whatsapp_provider=wa_provider,
        task_scheduler=task_sched,
        id_generator=id_gen,
        clock=clock,
    )
    template_svc = whatsapp_template_service_module.WhatsappTemplateService(
        whatsapp_provider=wa_provider,
        whatsapp_connection_repository=wa_connection_repo,
        agent_profile_repository=agent_profile_repo,
        clock=clock,
        reminder_service=reminder_svc,
    )
    return (
        template_svc,
        reminder_svc,
        agent_profile_repo,
        wa_connection_repo,
        reminder_repo,
        wa_provider,
    )


def _seed_profile(
    agent_profile_repo: agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
    *,
    attendance_name: str | None = None,
    payment_name: str | None = None,
) -> None:
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="prompt",
            appointment_reminder_enabled=False,
            appointment_reminder_attendance_template_name=attendance_name,
            appointment_reminder_payment_template_name=payment_name,
            updated_at=_NOW,
        )
    )


# ---------------------------------------------------------------------------
# activate_official_template
# ---------------------------------------------------------------------------


def test_activate_official_template_creates_meta_and_persists_attendance_name() -> None:
    template_svc, _, agent_profile_repo, _, _, _ = _build_context()
    _seed_profile(agent_profile_repo)

    result = template_svc.activate_official_template("tenant-1", "ATTENDANCE")

    assert result.kind == "ATTENDANCE"
    assert result.name == official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["ATTENDANCE"].name
    assert result.meta_status == "PENDING"

    updated_profile = agent_profile_repo.get_by_tenant_id("tenant-1")
    assert updated_profile is not None
    assert (
        updated_profile.appointment_reminder_attendance_template_name
        == official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["ATTENDANCE"].name
    )


def test_activate_official_template_creates_meta_and_persists_payment_name() -> None:
    template_svc, _, agent_profile_repo, _, _, _ = _build_context()
    _seed_profile(agent_profile_repo)

    result = template_svc.activate_official_template("tenant-1", "PAYMENT")

    assert result.kind == "PAYMENT"
    assert result.name == official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["PAYMENT"].name

    updated_profile = agent_profile_repo.get_by_tenant_id("tenant-1")
    assert updated_profile is not None
    assert (
        updated_profile.appointment_reminder_payment_template_name
        == official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["PAYMENT"].name
    )


def test_activate_official_template_raises_when_profile_not_found() -> None:
    template_svc, _, _, _, _, _ = _build_context()
    # No profile seeded.
    with pytest.raises(service_exceptions.EntityNotFoundError):
        template_svc.activate_official_template("tenant-1", "ATTENDANCE")


# ---------------------------------------------------------------------------
# deactivate_official_template
# ---------------------------------------------------------------------------


def test_deactivate_cancels_pending_reminders_and_clears_profile_name() -> None:
    template_svc, reminder_svc, agent_profile_repo, _, reminder_repo, _ = _build_context()
    attendance_name = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["ATTENDANCE"].name
    _seed_profile(agent_profile_repo, attendance_name=attendance_name)

    # Enable reminders so we can schedule one.
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="prompt",
            appointment_reminder_enabled=True,
            appointment_reminder_days_before=2,
            appointment_reminder_attendance_template_name=attendance_name,
            updated_at=_NOW,
        )
    )
    reminder_svc.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PAID",
    )
    pending_before = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    assert len(pending_before) == 1

    template_svc.deactivate_official_template("tenant-1", "ATTENDANCE")

    # Reminder should be cancelled.
    cancelled = reminder_repo.list_by_tenant("tenant-1", status="CANCELLED")
    assert len(cancelled) == 1

    # Profile should have no attendance template.
    updated_profile = agent_profile_repo.get_by_tenant_id("tenant-1")
    assert updated_profile is not None
    assert updated_profile.appointment_reminder_attendance_template_name is None


# ---------------------------------------------------------------------------
# list_official_template_status
# ---------------------------------------------------------------------------


def test_list_official_status_returns_not_created_when_profile_has_no_name() -> None:
    template_svc, _, agent_profile_repo, _, _, _ = _build_context()
    _seed_profile(agent_profile_repo)

    result = template_svc.list_official_template_status("tenant-1")

    assert len(result.items) == 2
    for item in result.items:
        assert item.meta_status == "NOT_CREATED"


def test_list_official_status_returns_meta_status_when_template_exists_in_meta() -> None:
    template_svc, _, agent_profile_repo, _, _, wa_provider = _build_context()
    attendance_name = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["ATTENDANCE"].name
    _seed_profile(agent_profile_repo, attendance_name=attendance_name)

    # Make Meta return an APPROVED template.
    import src.services.dto.whatsapp_template_dto as whatsapp_template_dto

    wa_provider.list_message_templates = lambda access_token, waba_id: [  # type: ignore[method-assign]
        whatsapp_template_dto.TemplateDTO(
            id="tmpl-id-1",
            name=attendance_name,
            category="UTILITY",
            language="es",
            status="APPROVED",
            components=[],
        )
    ]

    result = template_svc.list_official_template_status("tenant-1")

    attendance_item = next(i for i in result.items if i.kind == "ATTENDANCE")
    payment_item = next(i for i in result.items if i.kind == "PAYMENT")

    assert attendance_item.meta_status == "APPROVED"
    assert payment_item.meta_status == "NOT_CREATED"


# ---------------------------------------------------------------------------
# delete_template — guard for official active
# ---------------------------------------------------------------------------


def test_delete_template_rejects_official_attendance_when_active() -> None:
    template_svc, _, agent_profile_repo, _, _, _ = _build_context()
    attendance_name = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["ATTENDANCE"].name
    _seed_profile(agent_profile_repo, attendance_name=attendance_name)

    with pytest.raises(service_exceptions.OfficialTemplateActiveError):
        template_svc.delete_template("tenant-1", attendance_name)


def test_delete_template_allows_non_official_template() -> None:
    template_svc, _, agent_profile_repo, _, _, _ = _build_context()
    _seed_profile(agent_profile_repo)

    # Should not raise — custom templates not blocked.
    template_svc.delete_template("tenant-1", "my_custom_template")
