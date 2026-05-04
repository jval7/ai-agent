import httpx
import pytest

import src.adapters.outbound.email_resend.resend_email_notifier_adapter as resend_adapter
import src.infra.settings as app_settings
import src.services.exceptions as service_exceptions


def _make_settings(api_key: str = "re_test_key") -> app_settings.Settings:
    return app_settings.Settings(
        jwt_secret="test-secret",
        jwt_access_ttl_seconds=600,
        jwt_refresh_ttl_seconds=3600,
        default_system_prompt="prompt",
        conversation_context_messages=12,
        firestore_database_id="(default)",
        cors_allowed_origins=["http://localhost:5173"],
        frontend_app_base_url="http://localhost:5173",
        enable_dev_endpoints=True,
        meta_app_id="",
        meta_app_secret="",
        meta_redirect_uri="",
        meta_webhook_verify_token="",
        meta_api_version="v23.0",
        meta_config_id="",
        google_oauth_client_id="",
        google_oauth_client_secret="",
        google_oauth_redirect_uri="",
        google_cloud_project_id="test-project",
        gemini_location="us-central1",
        gemini_model="gemini-2.5-flash",
        gemini_max_output_tokens=2048,
        langsmith_tracing_enabled=False,
        langsmith_project="test",
        langsmith_api_key=None,
        langsmith_endpoint=None,
        langsmith_workspace_id=None,
        langsmith_environment=None,
        langsmith_tags=[],
        log_level="INFO",
        log_include_request_summary=False,
        cloud_tasks_location="us-central1",
        cloud_tasks_queue_id="tasks",
        cloud_run_base_url="",
        auto_close_delay_seconds=3600,
        rate_limit_enabled=False,
        whatsapp_outbound_noop=False,
        resend_api_key=api_key,
        resend_from_email="no-reply@agendachat.app",
        resend_from_name="Agendachat",
        invitation_account_setup_ttl_hours=168,
        invitation_password_reset_ttl_minutes=30,
        email_notifier_enabled=True,
    )


def _make_success_transport(email_id: str = "test-email-id-123") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": email_id})

    return httpx.MockTransport(handler)


def test_send_account_invitation_success() -> None:
    settings = _make_settings()
    client = httpx.Client(transport=_make_success_transport())
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    adapter.send_account_invitation(
        to_email="doc@acme.com",
        to_name="Dr. Acme",
        invitation_url="http://localhost:5173/accept-invite?token=abc123",
        tenant_name="Acme",
    )


def test_send_password_reset_success() -> None:
    settings = _make_settings()
    client = httpx.Client(transport=_make_success_transport())
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    adapter.send_password_reset(
        to_email="doc@acme.com",
        reset_url="http://localhost:5173/reset-password?token=xyz",
    )


def test_send_welcome_success() -> None:
    settings = _make_settings()
    client = httpx.Client(transport=_make_success_transport())
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    adapter.send_welcome(
        to_email="doc@acme.com",
        to_name="Dr. Acme",
        tenant_name="Acme",
        login_url="http://localhost:5173",
    )


def test_raises_external_provider_error_on_4xx() -> None:
    settings = _make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "invalid from address"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    with pytest.raises(service_exceptions.ExternalProviderError):
        adapter.send_password_reset(
            to_email="doc@acme.com",
            reset_url="http://localhost:5173/reset-password?token=xyz",
        )


def test_raises_external_provider_error_on_5xx() -> None:
    settings = _make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal server error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    with pytest.raises(service_exceptions.ExternalProviderError):
        adapter.send_account_invitation(
            to_email="doc@acme.com",
            to_name=None,
            invitation_url="http://localhost:5173/accept-invite?token=abc",
            tenant_name="Acme",
        )


def test_raises_external_provider_error_when_no_api_key() -> None:
    settings = _make_settings(api_key="")
    settings.resend_api_key = None
    client = httpx.Client(transport=_make_success_transport())
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    with pytest.raises(service_exceptions.ExternalProviderError, match="api key"):
        adapter.send_welcome(
            to_email="doc@acme.com",
            to_name=None,
            tenant_name="Acme",
            login_url="http://localhost:5173",
        )


def test_raises_external_provider_error_when_no_id_in_response() -> None:
    settings = _make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = resend_adapter.ResendEmailNotifierAdapter(settings=settings, http_client=client)

    with pytest.raises(service_exceptions.ExternalProviderError, match="email id"):
        adapter.send_welcome(
            to_email="doc@acme.com",
            to_name=None,
            tenant_name="Acme",
            login_url="http://localhost:5173",
        )
