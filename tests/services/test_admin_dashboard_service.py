import datetime
import typing

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.manual_appointment_repository_adapter as manual_appointment_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.scheduled_reminder_repository_adapter as scheduled_reminder_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.manual_appointment as manual_appointment_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.services.use_cases.admin_dashboard_service as admin_dashboard_service

_REAL_NOW = datetime.datetime.now(tz=datetime.UTC)
_NOW = _REAL_NOW.replace(day=15, hour=12, minute=0, second=0, microsecond=0)
_MONTH_START = _NOW.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _build_store() -> in_memory_store.InMemoryStore:
    return in_memory_store.InMemoryStore()


def _build_service(
    store: in_memory_store.InMemoryStore,
) -> admin_dashboard_service.AdminDashboardService:
    return admin_dashboard_service.AdminDashboardService(
        tenant_repository=tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store),
        user_repository=user_repository_adapter.InMemoryUserRepositoryAdapter(store),
        patient_repository=patient_repository_adapter.InMemoryPatientRepositoryAdapter(store),
        conversation_repository=conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
            store
        ),
        manual_appointment_repository=manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter(
            store
        ),
        scheduling_repository=scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(
            store
        ),
        scheduled_reminder_repository=scheduled_reminder_repository_adapter.InMemoryScheduledReminderRepositoryAdapter(),
    )


def _make_tenant(
    tenant_id: str,
    name: str,
    *,
    is_admin: bool = False,
    professional_name: str | None = None,
) -> tenant_entity.Tenant:
    return tenant_entity.Tenant(
        id=tenant_id,
        name=name,
        is_admin_tenant=is_admin,
        professional_name=professional_name,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_user(tenant_id: str) -> user_entity.User:
    return user_entity.User(
        id=f"user-{tenant_id}",
        tenant_id=tenant_id,
        email=f"owner-{tenant_id}@example.com",
        password_hash="hashed",
        role="professional",
        is_active=True,
        created_at=_NOW,
    )


def _make_patient(tenant_id: str, patient_id: str) -> patient_entity.Patient:
    return patient_entity.Patient(
        tenant_id=tenant_id,
        whatsapp_user_id=f"wa-{patient_id}",
        first_name="Test",
        last_name="Patient",
        email=f"patient-{patient_id}@example.com",
        age=30,
        location="Bogotá",
        phone="+573001234567",
        created_at=_NOW,
    )


def _make_conversation(
    tenant_id: str,
    conversation_id: str,
    *,
    updated_at: datetime.datetime | None = None,
    control_mode: typing.Literal["AI", "HUMAN"] = "AI",
) -> conversation_entity.Conversation:
    return conversation_entity.Conversation(
        id=conversation_id,
        tenant_id=tenant_id,
        whatsapp_user_id=f"wa-conv-{conversation_id}",
        control_mode=control_mode,
        started_at=_NOW,
        last_message_preview=None,
        message_ids=[],
        updated_at=updated_at or _NOW,
    )


def _make_appointment(
    tenant_id: str,
    appt_id: str,
    *,
    status: typing.Literal["SCHEDULED", "CANCELLED"] = "SCHEDULED",
    payment_status: typing.Literal["PENDING", "PAID"] = "PENDING",
    payment_amount_cop: int | None = None,
    payment_updated_at: datetime.datetime | None = None,
) -> manual_appointment_entity.ManualAppointment:
    _end = _NOW + datetime.timedelta(hours=1)
    return manual_appointment_entity.ManualAppointment(
        id=appt_id,
        tenant_id=tenant_id,
        patient_whatsapp_user_id="wa-appt",
        start_at=_NOW,
        end_at=_end,
        timezone="America/Bogota",
        summary="Appointment",
        calendar_event_id=None,
        status=status,
        payment_status=payment_status,
        payment_amount_cop=payment_amount_cop,
        payment_updated_at=payment_updated_at,
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_tenant_summaries_excludes_admin_tenant() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("admin-t", "__admin__", is_admin=True))
    tenant_repo.save(_make_tenant("pro-t", "Clínica Pro"))
    service = _build_service(store)

    summaries = service.list_tenant_summaries()

    assert len(summaries) == 1
    assert summaries[0].tenant_id == "pro-t"
    assert summaries[0].tenant_name == "Clínica Pro"


def test_list_tenant_summaries_search_filters_by_name() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("t1", "Clínica Alpha"))
    tenant_repo.save(_make_tenant("t2", "Centro Beta"))
    service = _build_service(store)

    summaries = service.list_tenant_summaries(search="alpha")

    assert len(summaries) == 1
    assert summaries[0].tenant_id == "t1"


def test_get_tenant_summary_aggregates_counts() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("t1", "Test Clinic"))

    patient_repo = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    patient_repo.save(_make_patient("t1", "p1"))
    patient_repo.save(_make_patient("t1", "p2"))

    conv_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    conv_repo.save_conversation(_make_conversation("t1", "c1"))

    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    user_repo.save(_make_user("t1"))

    service = _build_service(store)
    summary = service.get_tenant_summary("t1")

    assert summary is not None
    assert summary.patient_count == 2
    assert summary.conversation_count == 1
    assert summary.owner_email == "owner-t1@example.com"
    assert summary.owner_is_active is True


def test_get_tenant_summary_returns_none_for_admin_tenant() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("admin-t", "__admin__", is_admin=True))
    service = _build_service(store)

    result = service.get_tenant_summary("admin-t")

    assert result is None


def test_get_global_metrics_aggregates_across_tenants() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("t1", "Clinic A"))
    tenant_repo.save(_make_tenant("t2", "Clinic B"))

    patient_repo = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    patient_repo.save(_make_patient("t1", "p1"))
    patient_repo.save(_make_patient("t2", "p2"))
    patient_repo.save(_make_patient("t2", "p3"))

    conv_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    conv_repo.save_conversation(_make_conversation("t1", "c1", control_mode="AI"))
    conv_repo.save_conversation(_make_conversation("t2", "c2", control_mode="HUMAN"))
    conv_repo.save_conversation(_make_conversation("t2", "c3", control_mode="AI"))

    service = _build_service(store)
    metrics = service.get_global_metrics()

    assert metrics.tenants_count == 2
    assert metrics.total_patients == 3
    assert metrics.total_conversations == 3
    assert metrics.control_mode_distribution.get("AI", 0) == 2
    assert metrics.control_mode_distribution.get("HUMAN", 0) == 1


def _make_scheduling_request(
    tenant_id: str,
    request_id: str,
    *,
    payment_status: typing.Literal["PENDING", "PAID"] = "PENDING",
    payment_amount_cop: int | None = None,
    payment_updated_at: datetime.datetime | None = None,
) -> scheduling_request_entity.SchedulingRequest:
    return scheduling_request_entity.SchedulingRequest(
        id=request_id,
        tenant_id=tenant_id,
        conversation_id=f"conv-{request_id}",
        whatsapp_user_id=f"wa-req-{request_id}",
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
        payment_status=payment_status,
        payment_amount_cop=payment_amount_cop,
        payment_updated_at=payment_updated_at,
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_build_tenant_summary_revenue_this_month() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("t1", "Revenue Clinic"))

    appt_repo = manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter(
        store
    )
    # Paid this month
    appt_repo.save(
        _make_appointment(
            "t1",
            "a1",
            status="SCHEDULED",
            payment_status="PAID",
            payment_amount_cop=150000,
            payment_updated_at=_NOW,
        )
    )
    # Paid last month (should NOT count)
    last_month = _MONTH_START - datetime.timedelta(days=1)
    appt_repo.save(
        _make_appointment(
            "t1",
            "a2",
            status="SCHEDULED",
            payment_status="PAID",
            payment_amount_cop=50000,
            payment_updated_at=last_month,
        )
    )
    # Not paid (should NOT count)
    appt_repo.save(
        _make_appointment(
            "t1",
            "a3",
            status="SCHEDULED",
            payment_status="PENDING",
            payment_amount_cop=75000,
        )
    )

    service = _build_service(store)
    summary = service.get_tenant_summary("t1")

    assert summary is not None
    assert summary.total_revenue_cop_this_month == 150000


def test_build_tenant_summary_revenue_includes_scheduling_requests() -> None:
    store = _build_store()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(_make_tenant("t1", "Mixed Revenue Clinic"))

    appt_repo = manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter(
        store
    )
    appt_repo.save(
        _make_appointment(
            "t1",
            "a1",
            payment_status="PAID",
            payment_amount_cop=100000,
            payment_updated_at=_NOW,
        )
    )

    sched_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    sched_repo.save_request(
        _make_scheduling_request(
            "t1",
            "sr1",
            payment_status="PAID",
            payment_amount_cop=80000,
            payment_updated_at=_NOW,
        )
    )
    # Unpaid request should NOT count
    sched_repo.save_request(
        _make_scheduling_request(
            "t1",
            "sr2",
            payment_status="PENDING",
            payment_amount_cop=50000,
        )
    )

    service = _build_service(store)
    summary = service.get_tenant_summary("t1")

    assert summary is not None
    assert summary.total_revenue_cop_this_month == 180000


def test_patient_count_by_tenant() -> None:
    store = _build_store()
    patient_repo = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    patient_repo.save(_make_patient("t1", "p1"))
    patient_repo.save(_make_patient("t1", "p2"))
    patient_repo.save(_make_patient("t2", "p3"))

    assert patient_repo.count_by_tenant("t1") == 2
    assert patient_repo.count_by_tenant("t2") == 1
    assert patient_repo.count_by_tenant("t99") == 0


def test_conversation_count_and_active_since() -> None:
    store = _build_store()
    conv_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    yesterday = _NOW - datetime.timedelta(days=1)
    conv_repo.save_conversation(_make_conversation("t1", "c1", updated_at=_NOW))
    conv_repo.save_conversation(_make_conversation("t1", "c2", updated_at=yesterday))
    conv_repo.save_conversation(_make_conversation("t2", "c3", updated_at=_NOW))

    assert conv_repo.count_conversations("t1") == 2
    assert conv_repo.count_conversations("t2") == 1
    today_start = _NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    assert conv_repo.count_active_since("t1", today_start) == 1
    assert conv_repo.get_latest_activity("t1") == _NOW
    assert conv_repo.get_latest_activity("t99") is None


def test_manual_appointment_count_and_sum() -> None:
    store = _build_store()
    appt_repo = manual_appointment_repository_adapter.InMemoryManualAppointmentRepositoryAdapter(
        store
    )
    appt_repo.save(
        _make_appointment(
            "t1",
            "a1",
            status="SCHEDULED",
            payment_status="PAID",
            payment_amount_cop=100000,
            payment_updated_at=_NOW,
        )
    )
    appt_repo.save(_make_appointment("t1", "a2", status="CANCELLED"))

    assert appt_repo.count_by_tenant("t1") == 2
    assert appt_repo.count_by_tenant("t1", status="SCHEDULED") == 1
    assert appt_repo.sum_paid_revenue_since("t1", _MONTH_START) == 100000
    assert appt_repo.sum_paid_revenue_since("t1", _NOW + datetime.timedelta(days=1)) == 0
