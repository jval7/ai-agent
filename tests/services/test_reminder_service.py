import datetime
import zoneinfo

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.scheduled_reminder_repository_adapter as scheduled_reminder_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as task_scheduler_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.official_reminder_templates as official_reminder_templates
import src.services.exceptions as service_exceptions
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


def _build_service_with_conversation_repos(
    id_values: list[str],
    agent_profile: agent_profile_entity.AgentProfile | None = None,
) -> tuple[
    reminder_service_module.ReminderService,
    scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
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
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
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
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
    )
    return service, reminder_repo, scheduling_repo, conversation_repo, wa_provider


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
# reminder_scheduled_for computation (hora 12pm Bogota, no domingos)
# ---------------------------------------------------------------------------


def test_maybe_schedule_forces_noon_bogota_and_shifts_sunday_to_saturday() -> None:
    """Cita lunes → base es domingo → corre a sábado 12pm Bogota."""
    profile = _make_profile(attendance_name="appointment_reminder_attendance", days_before=1)
    service, _, reminder_repo, _, _ = _build_service(["reminder-1"], agent_profile=profile)

    # Cita lunes 2026-01-05 10am Bogota (= 15:00 UTC).
    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 5, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-monday",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=appointment,
        payment_status="PAID",
    )

    reminders = reminder_repo.list_by_tenant("tenant-1")
    assert len(reminders) == 1
    scheduled_for = reminders[0].reminder_scheduled_for.astimezone(bogota)
    assert scheduled_for == datetime.datetime(2026, 1, 3, 12, 0, tzinfo=bogota)  # Sábado 12pm
    assert scheduled_for.weekday() == 5  # Saturday


def test_maybe_schedule_forces_noon_bogota_when_no_sunday_shift_needed() -> None:
    """Cita viernes → base es miércoles → se queda miércoles 12pm Bogota."""
    profile = _make_profile(attendance_name="appointment_reminder_attendance", days_before=2)
    service, _, reminder_repo, _, _ = _build_service(["reminder-1"], agent_profile=profile)

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    # Cita viernes 2026-01-09 07:30 Bogota (hora arbitraria temprana).
    appointment = datetime.datetime(2026, 1, 9, 7, 30, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-friday",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=appointment,
        payment_status="PAID",
    )

    reminders = reminder_repo.list_by_tenant("tenant-1")
    assert len(reminders) == 1
    scheduled_for = reminders[0].reminder_scheduled_for.astimezone(bogota)
    # Miércoles 2026-01-07 12:00 Bogota (no domingo, solo normaliza la hora).
    assert scheduled_for == datetime.datetime(2026, 1, 7, 12, 0, tzinfo=bogota)
    assert scheduled_for.weekday() == 2  # Wednesday


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


# ---------------------------------------------------------------------------
# execute_reminder — body_parameters por kind
# ---------------------------------------------------------------------------


_ATTENDANCE_CANONICAL_NAME = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES[
    "ATTENDANCE"
].name
_PAYMENT_CANONICAL_NAME = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["PAYMENT"].name


def _build_profile_with_payment_details(
    payment_details_text: str | None = "Nequi 300 / Bancolombia 12345",
    office_location: agent_profile_entity.OfficeLocation | None = None,
) -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="tenant-1",
        system_prompt="prompt",
        appointment_reminder_enabled=True,
        appointment_reminder_days_before=1,
        appointment_reminder_attendance_template_name=_ATTENDANCE_CANONICAL_NAME,
        appointment_reminder_payment_template_name=_PAYMENT_CANONICAL_NAME,
        payment_details_text=payment_details_text,
        office_location=office_location,
        updated_at=_NOW,
    )


def test_execute_reminder_attendance_builds_natural_date_and_modality_virtual() -> None:
    profile = _build_profile_with_payment_details()
    service, _, reminder_repo, _, wa_provider = _build_service(
        ["reminder-1"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)  # Saturday

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Juan",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="VIRTUAL",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    assert len(pending) == 1
    reminder_id = pending[0].id

    result = service.execute_reminder("tenant-1", reminder_id)
    assert result["status"] == "sent"

    assert len(wa_provider.sent_messages) == 1
    sent = wa_provider.sent_messages[0]
    body = wa_provider.sent_template_body_parameters[0]
    assert sent["template_name"] == _ATTENDANCE_CANONICAL_NAME
    assert body[0] == "Juan"
    # days_diff from _NOW (2026-01-01) to the reminder_scheduled_for (Saturday 2026-01-02 12pm Bogota)
    # isn't what we assert — we only check the modality mapping.
    assert body[2] == "virtual por Google Meet"


def test_execute_reminder_attendance_maps_presencial_and_missing_modality() -> None:
    profile = _build_profile_with_payment_details()
    service, _, reminder_repo, _, wa_provider = _build_service(
        ["reminder-1", "reminder-2"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Ana",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="PRESENCIAL",
    )
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-2",
        patient_whatsapp_user_id="wa-user-2",
        patient_name="Luis",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality=None,
    )

    pending = sorted(reminder_repo.list_by_tenant("tenant-1", status="PENDING"), key=lambda r: r.id)
    assert len(pending) == 2

    service.execute_reminder("tenant-1", pending[0].id)
    service.execute_reminder("tenant-1", pending[1].id)

    presencial_body, fallback_body = wa_provider.sent_template_body_parameters
    assert presencial_body[2] == "presencial"
    # None modality fallback: also "presencial" (safer default).
    assert fallback_body[2] == "presencial"


def test_execute_reminder_attendance_virtual_includes_meet_url() -> None:
    profile = _build_profile_with_payment_details()
    service, _, reminder_repo, _, wa_provider = _build_service(
        ["reminder-1"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Juan",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="VIRTUAL",
        meet_url="https://meet.google.com/abc-defg-hij",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    service.execute_reminder("tenant-1", pending[0].id)

    body = wa_provider.sent_template_body_parameters[0]
    assert body[2] == "virtual por Google Meet (link: https://meet.google.com/abc-defg-hij)"


def test_execute_reminder_attendance_presencial_includes_office_location() -> None:
    profile = _build_profile_with_payment_details(
        office_location=agent_profile_entity.OfficeLocation(
            address="Av Siempre Viva 1234",
            arrival_instructions="Llegar 20 min antes con cédula",
        )
    )
    service, _, reminder_repo, _, wa_provider = _build_service(
        ["reminder-1"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Ana",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="PRESENCIAL",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    service.execute_reminder("tenant-1", pending[0].id)

    body = wa_provider.sent_template_body_parameters[0]
    assert body[2] == "presencial. Dirección: Av Siempre Viva 1234. Llegar 20 min antes con cédula"


def test_execute_reminder_payment_injects_payment_details_from_profile() -> None:
    profile = _build_profile_with_payment_details(
        payment_details_text="Nequi 300 111 2222\nBancolombia ahorros 9999-8888"
    )
    service, _, reminder_repo, _, wa_provider = _build_service(
        ["reminder-1"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Sofía",
        appointment_start_at=appointment,
        payment_status="PENDING",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    service.execute_reminder("tenant-1", pending[0].id)

    sent = wa_provider.sent_messages[0]
    body = wa_provider.sent_template_body_parameters[0]
    assert sent["template_name"] == _PAYMENT_CANONICAL_NAME
    assert body[0] == "Sofía"
    # Newlines are sanitized to a visible separator so Meta does not reject
    # the template (error 132018: param text cannot have new-line/tab).
    assert body[2] == "Nequi 300 111 2222 · Bancolombia ahorros 9999-8888"
    assert "\n" not in body[2]
    assert "\t" not in body[2]


def test_execute_reminder_payment_fails_when_details_missing() -> None:
    profile = _build_profile_with_payment_details(payment_details_text=None)
    service, _, reminder_repo, _, wa_provider = _build_service(
        ["reminder-1"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Jane",
        appointment_start_at=appointment,
        payment_status="PENDING",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    result = service.execute_reminder("tenant-1", pending[0].id)

    assert result["status"] == "skipped"
    assert result["reason"] == "payment_details_missing"
    assert wa_provider.sent_messages == []

    failed = reminder_repo.list_by_tenant("tenant-1", status="FAILED")
    assert len(failed) == 1
    assert failed[0].failure_reason == "payment_details_not_configured"


# ---------------------------------------------------------------------------
# execute_reminder — pre-positioning conversation state
# ---------------------------------------------------------------------------


def _setup_conversation(
    conversation_repo: conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
) -> None:
    """Create a minimal conversation so the reminder service can pre-position state."""
    conversation_repo.save_conversation(
        conversation_entity.Conversation(
            id="conv-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=_NOW,
            updated_at=_NOW,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )


def test_execute_reminder_attendance_creates_awaiting_attendance_request() -> None:
    """After sending an ATTENDANCE reminder, a new AWAITING_ATTENDANCE_CONFIRMATION request is created."""
    profile = _build_profile_with_payment_details()
    # IDs: reminder-1 (maybe_schedule), new_request-1, outbound_msg-1 (pre-position)
    service, reminder_repo, scheduling_repo, conversation_repo, _ = (
        _build_service_with_conversation_repos(
            ["reminder-1", "new-request-1", "outbound-msg-1"], agent_profile=profile
        )
    )
    _setup_conversation(conversation_repo)

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="SCHEDULING_REQUEST",
        source_id="sched-req-original",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Juan",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="VIRTUAL",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    assert len(pending) == 1

    result = service.execute_reminder("tenant-1", pending[0].id)

    assert result["status"] == "sent"

    # New SchedulingRequest should be created in the right state.
    requests = scheduling_repo.list_requests_by_conversation("tenant-1", "conv-1")
    assert len(requests) == 1
    new_req = requests[0]
    assert new_req.status == "AWAITING_ATTENDANCE_CONFIRMATION"
    assert new_req.source_appointment_id == "sched-req-original"

    # An outbound message should be persisted in the conversation.
    messages = conversation_repo.list_messages("tenant-1", "conv-1")
    assert len(messages) == 1
    assert messages[0].direction == "OUTBOUND"
    assert messages[0].role == "assistant"
    assert "Juan" in messages[0].content


def test_execute_reminder_payment_creates_awaiting_payment_request() -> None:
    """After sending a PAYMENT reminder, a new AWAITING_PAYMENT_CONFIRMATION request is created."""
    profile = _build_profile_with_payment_details(payment_details_text="Nequi 300 111 2222")
    # IDs: reminder-1 (maybe_schedule), new_request-1, outbound_msg-1 (pre-position)
    service, reminder_repo, scheduling_repo, conversation_repo, _ = (
        _build_service_with_conversation_repos(
            ["reminder-1", "new-request-1", "outbound-msg-1"], agent_profile=profile
        )
    )
    _setup_conversation(conversation_repo)

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="SCHEDULING_REQUEST",
        source_id="sched-req-original",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Maria",
        appointment_start_at=appointment,
        payment_status="PENDING",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")

    result = service.execute_reminder("tenant-1", pending[0].id)

    assert result["status"] == "sent"

    requests = scheduling_repo.list_requests_by_conversation("tenant-1", "conv-1")
    assert len(requests) == 1
    new_req = requests[0]
    assert new_req.status == "AWAITING_PAYMENT_CONFIRMATION"
    assert new_req.source_appointment_id == "sched-req-original"

    messages = conversation_repo.list_messages("tenant-1", "conv-1")
    assert len(messages) == 1
    assert messages[0].direction == "OUTBOUND"


def test_execute_reminder_archives_existing_open_requests() -> None:
    """Pre-positioning archives open scheduling requests before creating the new one."""
    profile = _build_profile_with_payment_details()
    # IDs: reminder-1 (maybe_schedule), new_request-1, outbound_msg-1 (pre-position)
    service, reminder_repo, scheduling_repo, conversation_repo, _ = (
        _build_service_with_conversation_repos(
            ["reminder-1", "new-request-1", "outbound-msg-1"], agent_profile=profile
        )
    )
    _setup_conversation(conversation_repo)

    # Pre-seed an open scheduling request.
    existing_request = scheduling_request_entity.SchedulingRequest(
        id="existing-req-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="INITIAL",
        status="BOOKED",
        round_number=1,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        slots=[],
        slot_options_map={},
        selected_slot_id=None,
        calendar_event_id=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    scheduling_repo.save_request(existing_request)

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Pedro",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="PRESENCIAL",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")

    service.execute_reminder("tenant-1", pending[0].id)

    # The old BOOKED request should now be CANCELLED.
    archived = scheduling_repo.get_request_by_id("tenant-1", "existing-req-1")
    assert archived is not None
    assert archived.status == "CANCELLED"

    # A new AWAITING_ATTENDANCE_CONFIRMATION request should exist.
    all_requests = scheduling_repo.list_requests_by_conversation("tenant-1", "conv-1")
    new_requests = [r for r in all_requests if r.status == "AWAITING_ATTENDANCE_CONFIRMATION"]
    assert len(new_requests) == 1


def test_execute_reminder_provisions_conversation_when_patient_is_unknown() -> None:
    """If no conversation exists for the patient, pre-positioning materializes
    the WhatsappUser + Conversation pair so the bot has context when the
    patient replies. This is the common path for reminders sent to manual
    appointments of patients who never chatted before."""
    profile = _build_profile_with_payment_details()
    service, reminder_repo, scheduling_repo, conversation_repo, _wa_provider = (
        _build_service_with_conversation_repos(
            ["reminder-1", "new-conversation-1", "new-request-1", "outbound-msg-1"],
            agent_profile=profile,
        )
    )
    # No conversation is set up — patient is unknown.

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 3, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-unknown",
        patient_name="Unknown",
        appointment_start_at=appointment,
        payment_status="PAID",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")

    result = service.execute_reminder("tenant-1", pending[0].id)
    assert result["status"] == "sent"

    conversation = conversation_repo.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-unknown"
    )
    assert conversation is not None, "conversation should be auto-created"
    whatsapp_user = conversation_repo.get_whatsapp_user("tenant-1", "wa-user-unknown")
    assert whatsapp_user is not None
    assert whatsapp_user.display_name == "Unknown"

    requests = scheduling_repo.list_requests_by_tenant("tenant-1")
    assert len(requests) == 1
    assert requests[0].status == "AWAITING_ATTENDANCE_CONFIRMATION"


# ---------------------------------------------------------------------------
# send_reminder_now
# ---------------------------------------------------------------------------


def test_send_reminder_now_cancels_task_and_sends_immediately() -> None:
    profile = _build_profile_with_payment_details()
    service, _, reminder_repo, task_sched, wa_provider = _build_service(
        ["reminder-1"], agent_profile=profile
    )

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 5, 10, 0, tzinfo=bogota)

    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Ana",
        appointment_start_at=appointment,
        payment_status="PAID",
        appointment_modality="PRESENCIAL",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    assert len(pending) == 1
    assert len(task_sched.scheduled_tasks) == 1

    result = service.send_reminder_now("tenant-1", pending[0].id)

    assert result["status"] == "sent"
    assert len(wa_provider.sent_messages) == 1
    # Scheduled Cloud Task was cancelled to avoid a duplicate send later.
    assert task_sched.scheduled_tasks == []
    # Reminder state is transitioned to SENT.
    sent_reminder = reminder_repo.get_by_id("tenant-1", pending[0].id)
    assert sent_reminder is not None
    assert sent_reminder.status == "SENT"


def test_send_reminder_now_rejects_terminal_status() -> None:
    profile = _build_profile_with_payment_details()
    service, _, reminder_repo, _, _ = _build_service(["reminder-1"], agent_profile=profile)

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 5, 10, 0, tzinfo=bogota)
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Ana",
        appointment_start_at=appointment,
        payment_status="PAID",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    reminder = pending[0]
    reminder.status = "SENT"
    reminder_repo.save(reminder)

    with pytest.raises(service_exceptions.InvalidStateError):
        service.send_reminder_now("tenant-1", reminder.id)


def test_send_reminder_now_retries_failed_reminder() -> None:
    profile = _build_profile_with_payment_details()
    service, _, reminder_repo, _, whatsapp = _build_service(["reminder-1"], agent_profile=profile)

    bogota = zoneinfo.ZoneInfo("America/Bogota")
    appointment = datetime.datetime(2026, 1, 5, 10, 0, tzinfo=bogota)
    service.maybe_schedule_reminder(
        tenant_id="tenant-1",
        source_type="MANUAL_APPOINTMENT",
        source_id="appt-1",
        patient_whatsapp_user_id="wa-user-1",
        patient_name="Ana",
        appointment_start_at=appointment,
        payment_status="PAID",
    )
    pending = reminder_repo.list_by_tenant("tenant-1", status="PENDING")
    reminder = pending[0]
    reminder.status = "FAILED"
    reminder.failure_reason = "payment_details_not_configured"
    reminder_repo.save(reminder)

    result = service.send_reminder_now("tenant-1", reminder.id)

    assert result["status"] == "sent"
    refreshed = reminder_repo.get_by_id("tenant-1", reminder.id)
    assert refreshed is not None
    assert refreshed.status == "SENT"
    assert refreshed.failure_reason is None
    assert len(whatsapp.sent_template_body_parameters) == 1


def test_send_reminder_now_raises_when_reminder_missing() -> None:
    service, _, _, _, _ = _build_service([])

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.send_reminder_now("tenant-1", "unknown-id")
