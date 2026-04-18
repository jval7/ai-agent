import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.scheduled_reminder_repository_adapter as scheduled_reminder_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.use_cases.reminder_service as reminder_service_module
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_APPOINTMENT_FAR = datetime.datetime(2026, 1, 10, tzinfo=datetime.UTC)


def _build_service(
    id_values: list[str],
    agent_profile: agent_profile_entity.AgentProfile | None = None,
) -> tuple[
    reminder_service_module.ReminderService,
    agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter,
    scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter,
    task_scheduler_adapter.InMemoryTaskSchedulerAdapter,
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
    id_gen = fake_adapters.SequenceIdGenerator(id_values)

    wa_connection_repo.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=_NOW,
        )
    )

    if agent_profile is not None:
        agent_profile_repo.save(agent_profile)

    service = reminder_service_module.ReminderService(
        scheduled_reminder_repository=reminder_repo,
        agent_profile_repository=agent_profile_repo,
        whatsapp_connection_repository=wa_connection_repo,
        whatsapp_provider=wa_provider,
        task_scheduler=task_sched,
        id_generator=id_gen,
        clock=clock,
    )
    return service, agent_profile_repo, reminder_repo, task_sched, wa_provider


def _make_profile(
    *,
    attendance_name: str | None = "appointment_reminder_attendance",
    payment_name: str | None = None,
    enabled: bool = True,
    days_before: int = 2,
) -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="tenant-1",
        system_prompt="prompt",
        appointment_reminder_enabled=enabled,
        appointment_reminder_days_before=days_before if enabled else None,
        appointment_reminder_attendance_template_name=attendance_name,
        appointment_reminder_payment_template_name=payment_name,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# maybe_schedule_reminder
# ---------------------------------------------------------------------------


def test_maybe_schedule_uses_attendance_template_when_paid() -> None:
    profile = _make_profile(
        attendance_name="appointment_reminder_attendance",
        payment_name="appointment_reminder_payment",
    )
    service, _, reminder_repo, task_sched, _ = _build_service(["reminder-1"], agent_profile=profile)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PAID",
    )

    reminders = reminder_repo.list_by_tenant("tenant-1")
    assert len(reminders) == 1
    assert reminders[0].template_name == "appointment_reminder_attendance"
    assert len(task_sched.scheduled_tasks) == 1


def test_maybe_schedule_uses_payment_template_when_pending() -> None:
    profile = _make_profile(
        attendance_name="appointment_reminder_attendance",
        payment_name="appointment_reminder_payment",
    )
    service, _, reminder_repo, task_sched, _ = _build_service(["reminder-1"], agent_profile=profile)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PENDING",
    )

    reminders = reminder_repo.list_by_tenant("tenant-1")
    assert len(reminders) == 1
    assert reminders[0].template_name == "appointment_reminder_payment"
    assert len(task_sched.scheduled_tasks) == 1


def test_maybe_schedule_skips_when_attendance_template_missing_for_paid() -> None:
    """Service skips scheduling if the relevant template kind is not configured.

    The AgentProfile entity validator prevents enabled=True without attendance_template,
    so we test via model_construct to bypass validation — simulating a legacy profile
    or a future state where template was cleared without disabling reminders.
    """
    profile = agent_profile_entity.AgentProfile.model_construct(
        tenant_id="tenant-1",
        system_prompt="prompt",
        appointment_reminder_enabled=True,
        appointment_reminder_days_before=2,
        appointment_reminder_attendance_template_name=None,  # deliberately missing
        appointment_reminder_payment_template_name="appointment_reminder_payment",
        updated_at=_NOW,
    )
    service, _, reminder_repo, task_sched, _ = _build_service(["reminder-1"], agent_profile=profile)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PAID",
    )

    assert reminder_repo.list_by_tenant("tenant-1") == []
    assert task_sched.scheduled_tasks == []


def test_maybe_schedule_skips_when_payment_template_missing_for_pending() -> None:
    """PENDING but no payment template → skip without error."""
    profile = _make_profile(attendance_name="appointment_reminder_attendance", payment_name=None)
    service, _, reminder_repo, task_sched, _ = _build_service(["reminder-1"], agent_profile=profile)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PENDING",
    )

    assert reminder_repo.list_by_tenant("tenant-1") == []
    assert task_sched.scheduled_tasks == []


# ---------------------------------------------------------------------------
# swap_template_for_source
# ---------------------------------------------------------------------------


def test_swap_template_cancels_old_reminder_and_enqueues_new_preserving_scheduled_for() -> None:
    profile = _make_profile(
        attendance_name="appointment_reminder_attendance",
        payment_name="appointment_reminder_payment",
    )
    service, _, reminder_repo, _, _ = _build_service(
        ["reminder-1", "reminder-2"], agent_profile=profile
    )

    # Schedule a PAYMENT reminder first.
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PENDING",
    )

    old_reminders = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    assert len(old_reminders) == 1
    old_scheduled_for = old_reminders[0].reminder_scheduled_for
    assert old_reminders[0].template_name == "appointment_reminder_payment"

    # Now swap to ATTENDANCE template.
    service.swap_template_for_source(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        new_kind="ATTENDANCE",
    )

    all_reminders = reminder_repo.list_by_tenant("tenant-1")
    # The old reminder should be CANCELLED.
    cancelled = [r for r in all_reminders if r.status == "CANCELLED"]
    assert len(cancelled) == 1
    assert cancelled[0].failure_reason == "payment_status_changed"

    # A new PENDING reminder should exist with attendance template.
    pending = [r for r in all_reminders if r.status == "PENDING"]
    assert len(pending) == 1
    assert pending[0].template_name == "appointment_reminder_attendance"
    # Preserved the same reminder_scheduled_for.
    assert pending[0].reminder_scheduled_for == old_scheduled_for


def test_swap_template_skips_when_no_pending_reminders() -> None:
    profile = _make_profile(attendance_name="appointment_reminder_attendance", payment_name=None)
    service, _, reminder_repo, _, _ = _build_service(["reminder-1"], agent_profile=profile)

    # No reminders scheduled — swap should be a no-op.
    service.swap_template_for_source(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        new_kind="ATTENDANCE",
    )

    assert reminder_repo.list_by_tenant("tenant-1") == []


# ---------------------------------------------------------------------------
# cancel_reminders_by_template
# ---------------------------------------------------------------------------


def test_cancel_reminders_by_template_cancels_all_pending_with_that_template() -> None:
    profile = _make_profile(
        attendance_name="appointment_reminder_attendance",
        payment_name="appointment_reminder_payment",
    )
    service, _, reminder_repo, _, _ = _build_service(
        ["reminder-1", "reminder-2", "reminder-3"], agent_profile=profile
    )

    # Schedule two reminders with payment template and one with attendance.
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PENDING",
    )
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-2",
        patient_whatsapp_user_id="wa-user-2",
        patient_name="Bob",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PENDING",
    )
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-3",
        patient_whatsapp_user_id="wa-user-3",
        patient_name="Alice",
        appointment_start_at=_APPOINTMENT_FAR,
        payment_status="PAID",
    )

    pending_before = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    assert len(pending_before) == 3

    # Cancel all PAYMENT reminders.
    service.cancel_reminders_by_template("tenant-1", "appointment_reminder_payment")

    all_reminders = reminder_repo.list_by_tenant("tenant-1")
    cancelled = [r for r in all_reminders if r.status == "CANCELLED"]
    pending_after = [r for r in all_reminders if r.status == "PENDING"]

    assert len(cancelled) == 2
    assert all(r.failure_reason == "template_deactivated" for r in cancelled)
    assert len(pending_after) == 1
    assert pending_after[0].template_name == "appointment_reminder_attendance"
