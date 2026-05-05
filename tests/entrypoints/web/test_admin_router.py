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
import src.services.dto.patient_dto as patient_dto

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
