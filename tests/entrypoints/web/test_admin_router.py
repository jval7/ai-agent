import datetime
import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.admin_router as admin_router
import src.services.constants as service_constants
import src.services.dto.admin_dto as admin_dto
import src.services.dto.auth_dto as auth_dto
import src.services.dto.conversation_dto as conversation_dto
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.patient_dto as patient_dto
import src.services.dto.scheduling_dto as scheduling_dto

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

_ADMIN_CLAIMS = auth_dto.TokenClaimsDTO(
    sub="admin-user-1",
    tenant_id="admin-tenant-1",
    role=service_constants.ROLE_ADMIN,
    exp=2000000000,
    jti="jti-admin",
    token_kind="access",
)

_PROFESSIONAL_CLAIMS = auth_dto.TokenClaimsDTO(
    sub="prof-user-1",
    tenant_id="prof-tenant-1",
    role=service_constants.ROLE_PROFESSIONAL,
    exp=2000000000,
    jti="jti-prof",
    token_kind="access",
)


def _make_client(
    claims: auth_dto.TokenClaimsDTO = _ADMIN_CLAIMS,
    mock_container: unittest.mock.MagicMock | None = None,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(admin_router.router)

    container = mock_container or unittest.mock.MagicMock()

    def override_container() -> typing.Any:
        return container

    def override_claims() -> auth_dto.TokenClaimsDTO:
        return claims

    app.dependency_overrides[http_dependencies.get_container] = override_container
    app.dependency_overrides[http_dependencies.get_current_claims] = override_claims
    return fastapi.testclient.TestClient(app, raise_server_exceptions=True)


def _make_tenant_summary(tenant_id: str) -> admin_dto.TenantSummaryDTO:
    return admin_dto.TenantSummaryDTO(
        tenant_id=tenant_id,
        tenant_name="Test Clinic",
        professional_name=None,
        patient_count=5,
        conversation_count=3,
        active_conversations_today=1,
        manual_appointment_count_upcoming=2,
        pending_reminder_count=0,
        total_revenue_cop_this_month=0,
        last_activity_at=_NOW,
        owner_email="owner@test.com",
        owner_is_active=True,
    )


def _make_global_metrics() -> admin_dto.GlobalMetricsDTO:
    return admin_dto.GlobalMetricsDTO(
        tenants_count=3,
        tenants_active=2,
        total_patients=10,
        total_conversations=8,
        total_manual_appointments_upcoming=4,
        total_pending_reminders=1,
        control_mode_distribution={"AGENT": 5, "HUMAN": 3},
        top_tenants_by_conversations=[],
    )


# ---------------------------------------------------------------------------
# Role enforcement
# ---------------------------------------------------------------------------


def test_dashboard_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.get("/v1/admin/dashboard")
    assert response.status_code == 403


def test_list_tenants_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.get("/v1/admin/tenants")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_get_global_metrics_returns_metrics() -> None:
    container = unittest.mock.MagicMock()
    container.admin_dashboard_service.get_global_metrics.return_value = _make_global_metrics()

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["tenants_count"] == 3
    assert body["total_patients"] == 10


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


def test_list_tenants_returns_summaries() -> None:
    summary = _make_tenant_summary("t1")
    container = unittest.mock.MagicMock()
    container.admin_dashboard_service.list_tenant_summaries.return_value = [summary]

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["tenant_id"] == "t1"


def test_get_tenant_returns_summary() -> None:
    summary = _make_tenant_summary("t1")
    container = unittest.mock.MagicMock()
    container.admin_dashboard_service.get_tenant_summary.return_value = summary

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "t1"
    container.admin_dashboard_service.get_tenant_summary.assert_called_once_with("t1")


def test_get_tenant_returns_404_when_not_found() -> None:
    container = unittest.mock.MagicMock()
    container.admin_dashboard_service.get_tenant_summary.return_value = None

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/missing-tenant")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------


def test_list_patients_for_tenant_delegates_to_service() -> None:
    patient_list = patient_dto.PatientListResponseDTO(items=[])
    container = unittest.mock.MagicMock()
    container.patient_query_service.list_patients_for_tenant.return_value = patient_list

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/patients")

    assert response.status_code == 200
    container.patient_query_service.list_patients_for_tenant.assert_called_once_with(
        "t1", search=None
    )


def test_list_patients_for_tenant_passes_search_param() -> None:
    patient_list = patient_dto.PatientListResponseDTO(items=[])
    container = unittest.mock.MagicMock()
    container.patient_query_service.list_patients_for_tenant.return_value = patient_list

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/patients?search=juan")

    assert response.status_code == 200
    container.patient_query_service.list_patients_for_tenant.assert_called_once_with(
        "t1", search="juan"
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


def test_list_conversations_for_tenant_delegates_to_query_service() -> None:
    conv_list = conversation_dto.ConversationListResponseDTO(items=[])
    container = unittest.mock.MagicMock()
    container.conversation_query_service.list_conversations.return_value = conv_list

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/conversations")

    assert response.status_code == 200
    container.conversation_query_service.list_conversations.assert_called_once_with("t1")


def test_update_control_mode_delegates_to_control_service() -> None:
    mode_response = conversation_dto.ConversationControlModeResponseDTO(
        conversation_id="c1",
        tenant_id="t1",
        control_mode="HUMAN",
        updated_at=_NOW,
    )
    container = unittest.mock.MagicMock()
    container.conversation_control_service.update_control_mode_for_tenant.return_value = (
        mode_response
    )

    client = _make_client(mock_container=container)
    response = client.put(
        "/v1/admin/tenants/t1/conversations/c1/control-mode",
        json={"control_mode": "HUMAN"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["control_mode"] == "HUMAN"


# ---------------------------------------------------------------------------
# Manual appointments
# ---------------------------------------------------------------------------


def test_list_manual_appointments_for_tenant() -> None:
    from src.services.dto.manual_appointment_dto import ManualAppointmentListResponseDTO

    appt_list = ManualAppointmentListResponseDTO(items=[])
    container = unittest.mock.MagicMock()
    container.manual_appointment_service.list_appointments_for_tenant.return_value = appt_list

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/manual-appointments")

    assert response.status_code == 200
    container.manual_appointment_service.list_appointments_for_tenant.assert_called_once_with(
        "t1", None
    )


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------


def test_list_blacklist_for_tenant() -> None:
    from src.services.dto.blacklist_dto import BlacklistListResponseDTO

    bl_list = BlacklistListResponseDTO(items=[])
    container = unittest.mock.MagicMock()
    container.blacklist_service.list_entries_for_tenant.return_value = bl_list

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/blacklist")

    assert response.status_code == 200
    container.blacklist_service.list_entries_for_tenant.assert_called_once_with("t1")


def test_delete_blacklist_entry_for_tenant() -> None:
    container = unittest.mock.MagicMock()
    container.blacklist_service.delete_entry_for_tenant.return_value = None

    client = _make_client(mock_container=container)
    response = client.delete("/v1/admin/tenants/t1/blacklist/wa-user-1")

    assert response.status_code == 204
    container.blacklist_service.delete_entry_for_tenant.assert_called_once_with("t1", "wa-user-1")


# ---------------------------------------------------------------------------
# Configuration (agent)
# ---------------------------------------------------------------------------


def test_get_system_prompt_for_tenant() -> None:
    from src.services.dto.agent_dto import SystemPromptResponseDTO

    prompt_response = SystemPromptResponseDTO(tenant_id="t1", system_prompt="Hello world")
    container = unittest.mock.MagicMock()
    container.agent_service.get_system_prompt.return_value = prompt_response

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/agent/system-prompt")

    assert response.status_code == 200
    body = response.json()
    assert body["system_prompt"] == "Hello world"
    container.agent_service.get_system_prompt.assert_called_once_with("t1")


def test_get_agent_settings_for_tenant() -> None:
    from src.services.dto.agent_dto import AgentSettingsResponseDTO

    settings_response = AgentSettingsResponseDTO(
        tenant_id="t1",
        message_debounce_delay_seconds=5,
        assistant_enabled=True,
        appointment_reminder_enabled=False,
        appointment_reminder_days_before=None,
        appointment_reminder_attendance_template_name=None,
        appointment_reminder_payment_template_name=None,
        payment_details_text=None,
        office_location=None,
        payment_timing="BEFORE_SESSION",
    )
    container = unittest.mock.MagicMock()
    container.agent_service.get_agent_settings.return_value = settings_response

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/agent/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["assistant_enabled"] is True
    container.agent_service.get_agent_settings.assert_called_once_with("t1")


# ---------------------------------------------------------------------------
# Helpers for new endpoint tests
# ---------------------------------------------------------------------------


def _make_scheduling_request_summary(
    request_id: str = "req-1",
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    return scheduling_dto.SchedulingRequestSummaryDTO(
        request_id=request_id,
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="INITIAL",
        status="BOOKED",
        round_number=1,
        patient_preference_note=None,
        rejection_summary=None,
        professional_note=None,
        patient_first_name="Juan",
        patient_last_name="Perez",
        patient_age=30,
        consultation_reason="headache",
        consultation_details=None,
        appointment_modality="PRESENCIAL",
        patient_location=None,
        slot_options_map={},
        selected_slot_id="slot-1",
        calendar_event_id="event-1",
        payment_amount_cop=50000,
        payment_currency="COP",
        payment_method="CASH",
        payment_status="PENDING",
        payment_updated_at=None,
        created_at=_NOW,
        updated_at=_NOW,
        slots=[],
    )


def _make_gc_connection_status(
    tenant_id: str = "t1",
) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
    return google_calendar_dto.GoogleCalendarConnectionStatusDTO(
        tenant_id=tenant_id,
        status="CONNECTED",
        calendar_id="cal-123",
        professional_timezone="America/Bogota",
        connected_at=_NOW,
    )


# ---------------------------------------------------------------------------
# DELETE conversations/{conversation_id}/messages (reset_messages)
# ---------------------------------------------------------------------------


def test_reset_messages_for_tenant_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.delete("/v1/admin/tenants/t1/conversations/c1/messages")
    assert response.status_code == 403


def test_reset_messages_for_tenant_returns_204_in_dev_mode() -> None:
    container = unittest.mock.MagicMock()
    container.settings.enable_dev_endpoints = True
    container.conversation_control_service.reset_messages_for_tenant.return_value = None

    client = _make_client(mock_container=container)
    response = client.delete("/v1/admin/tenants/t1/conversations/c1/messages")

    assert response.status_code == 204
    container.conversation_control_service.reset_messages_for_tenant.assert_called_once_with(
        tenant_id="t1",
        conversation_id="c1",
    )


def test_reset_messages_for_tenant_blocked_outside_dev_mode() -> None:
    container = unittest.mock.MagicMock()
    container.settings.enable_dev_endpoints = False

    client = _make_client(mock_container=container)
    response = client.delete("/v1/admin/tenants/t1/conversations/c1/messages")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET scheduling/availability
# ---------------------------------------------------------------------------


def test_get_scheduling_availability_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.get(
        "/v1/admin/tenants/t1/scheduling/availability",
        params={"from": "2026-01-01T08:00:00Z", "to": "2026-01-01T18:00:00Z"},
    )
    assert response.status_code == 403


def test_get_scheduling_availability_delegates_to_service() -> None:
    availability = google_calendar_dto.GoogleCalendarAvailabilityResponseDTO(
        tenant_id="t1",
        calendar_id="cal-123",
        timezone="America/Bogota",
        busy_intervals=[],
    )
    container = unittest.mock.MagicMock()
    container.google_calendar_onboarding_service.get_availability.return_value = availability

    client = _make_client(mock_container=container)
    response = client.get(
        "/v1/admin/tenants/t1/scheduling/availability",
        params={"from": "2026-01-01T08:00:00Z", "to": "2026-01-01T18:00:00Z"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "t1"
    assert body["busy_intervals"] == []
    container.google_calendar_onboarding_service.get_availability.assert_called_once()


# ---------------------------------------------------------------------------
# POST conversations/{id}/scheduling/requests/{id}/reschedule
# ---------------------------------------------------------------------------


def test_reschedule_booked_slot_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.post(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/reschedule",
        json={
            "start_at": "2026-02-01T10:00:00Z",
            "end_at": "2026-02-01T11:00:00Z",
            "timezone": "America/Bogota",
        },
    )
    assert response.status_code == 403


def test_reschedule_booked_slot_delegates_to_service() -> None:
    summary = _make_scheduling_request_summary()
    container = unittest.mock.MagicMock()
    container.scheduling_service.reschedule_booked_slot.return_value = summary

    client = _make_client(mock_container=container)
    response = client.post(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/reschedule",
        json={
            "start_at": "2026-02-01T10:00:00Z",
            "end_at": "2026-02-01T11:00:00Z",
            "timezone": "America/Bogota",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    container.scheduling_service.reschedule_booked_slot.assert_called_once()
    call_kwargs = container.scheduling_service.reschedule_booked_slot.call_args.kwargs
    assert call_kwargs["tenant_id"] == "t1"
    assert call_kwargs["request_id"] == "req-1"


# ---------------------------------------------------------------------------
# DELETE conversations/{id}/scheduling/requests/{id}/booked-slot
# ---------------------------------------------------------------------------


def test_cancel_booked_slot_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.delete(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/booked-slot"
    )
    assert response.status_code == 403


def test_cancel_booked_slot_delegates_to_service() -> None:
    summary = _make_scheduling_request_summary()
    container = unittest.mock.MagicMock()
    container.scheduling_service.cancel_booked_slot.return_value = summary

    client = _make_client(mock_container=container)
    response = client.delete(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/booked-slot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    container.scheduling_service.cancel_booked_slot.assert_called_once()
    call_kwargs = container.scheduling_service.cancel_booked_slot.call_args.kwargs
    assert call_kwargs["tenant_id"] == "t1"
    assert call_kwargs["request_id"] == "req-1"


# ---------------------------------------------------------------------------
# PUT conversations/{id}/scheduling/requests/{id}/booked-payment
# ---------------------------------------------------------------------------


def test_update_booked_payment_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.put(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/booked-payment",
        json={
            "payment_amount_cop": 50000,
            "payment_currency": "COP",
            "payment_method": "CASH",
            "payment_status": "PAID",
        },
    )
    assert response.status_code == 403


def test_update_booked_payment_delegates_to_service() -> None:
    summary = _make_scheduling_request_summary()
    container = unittest.mock.MagicMock()
    container.scheduling_service.update_booked_payment.return_value = summary

    client = _make_client(mock_container=container)
    response = client.put(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/booked-payment",
        json={
            "payment_amount_cop": 50000,
            "payment_currency": "COP",
            "payment_method": "CASH",
            "payment_status": "PAID",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    container.scheduling_service.update_booked_payment.assert_called_once()
    call_kwargs = container.scheduling_service.update_booked_payment.call_args.kwargs
    assert call_kwargs["tenant_id"] == "t1"
    assert call_kwargs["request_id"] == "req-1"


# ---------------------------------------------------------------------------
# POST conversations/{id}/scheduling/requests/{id}/change-modality
# ---------------------------------------------------------------------------


def test_change_booked_slot_modality_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.post(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/change-modality",
        json={"new_modality": "VIRTUAL"},
    )
    assert response.status_code == 403


def test_change_booked_slot_modality_delegates_to_service() -> None:
    summary = _make_scheduling_request_summary()
    container = unittest.mock.MagicMock()
    container.scheduling_service.change_booked_modality.return_value = summary

    client = _make_client(mock_container=container)
    response = client.post(
        "/v1/admin/tenants/t1/conversations/c1/scheduling/requests/req-1/change-modality",
        json={"new_modality": "VIRTUAL"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    container.scheduling_service.change_booked_modality.assert_called_once()
    call_kwargs = container.scheduling_service.change_booked_modality.call_args.kwargs
    assert call_kwargs["tenant_id"] == "t1"
    assert call_kwargs["request_id"] == "req-1"


# ---------------------------------------------------------------------------
# POST conversations/{id}/scheduling/close-session
# ---------------------------------------------------------------------------


def test_close_scheduling_session_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.post("/v1/admin/tenants/t1/conversations/c1/scheduling/close-session")
    assert response.status_code == 403


def test_close_scheduling_session_delegates_to_service() -> None:
    container = unittest.mock.MagicMock()
    container.scheduling_service.close_session.return_value = {"status": "closed"}

    client = _make_client(mock_container=container)
    response = client.post("/v1/admin/tenants/t1/conversations/c1/scheduling/close-session")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    container.scheduling_service.close_session.assert_called_once_with(
        tenant_id="t1",
        conversation_id="c1",
    )


# ---------------------------------------------------------------------------
# GET google-calendar/connection
# ---------------------------------------------------------------------------


def test_get_google_calendar_connection_returns_403_for_professional_role() -> None:
    client = _make_client(claims=_PROFESSIONAL_CLAIMS)
    response = client.get("/v1/admin/tenants/t1/google-calendar/connection")
    assert response.status_code == 403


def test_get_google_calendar_connection_delegates_to_service() -> None:
    status = _make_gc_connection_status("t1")
    container = unittest.mock.MagicMock()
    container.google_calendar_onboarding_service.get_connection_status.return_value = status

    client = _make_client(mock_container=container)
    response = client.get("/v1/admin/tenants/t1/google-calendar/connection")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "t1"
    assert body["status"] == "CONNECTED"
    assert body["calendar_id"] == "cal-123"
    container.google_calendar_onboarding_service.get_connection_status.assert_called_once_with("t1")
