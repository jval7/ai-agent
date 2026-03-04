import base64

import httpx
import pytest

import src.adapters.outbound.secret_manager.app_config_secret_loader_adapter as adapter_module


class _FakeCredentials:
    def __init__(self, refreshed_token: str) -> None:
        self.token: str | None = None
        self._refreshed_token = refreshed_token
        self.refreshed = False

    def refresh(self, _request: object) -> None:
        self.refreshed = True
        self.token = self._refreshed_token


def test_load_reads_secret_json_from_secret_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_credentials = _FakeCredentials(refreshed_token="adc-token")
    captured_request: dict[str, str] = {}

    def fake_default(
        scopes: list[str],
    ) -> tuple[_FakeCredentials, str]:
        assert scopes == [adapter_module._SECRET_MANAGER_SCOPE]
        return fake_credentials, "ai-agent-calendar-2603011621"

    def fake_get(
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        captured_request["url"] = url
        captured_request["authorization"] = headers["Authorization"]
        assert timeout == 10.0
        payload = base64.b64encode(b'{"JWT_SECRET":"secret-from-sm"}').decode("utf-8")
        request = httpx.Request(method="GET", url=url)
        return httpx.Response(
            status_code=200,
            json={"payload": {"data": payload}},
            request=request,
        )

    monkeypatch.setattr(
        "src.adapters.outbound.secret_manager.app_config_secret_loader_adapter.google_auth.default",
        fake_default,
    )
    monkeypatch.setattr(
        "src.adapters.outbound.secret_manager.app_config_secret_loader_adapter.httpx.get",
        fake_get,
    )

    loader = adapter_module.SecretManagerAppConfigLoaderAdapter()
    loaded_secret = loader.load()

    assert fake_credentials.refreshed is True
    assert loaded_secret.project_id == "ai-agent-calendar-2603011621"
    assert loaded_secret.secret_json == '{"JWT_SECRET":"secret-from-sm"}'
    assert (
        captured_request["url"]
        == "https://secretmanager.googleapis.com/v1/projects/ai-agent-calendar-2603011621/"
        "secrets/AI_AGENT_APP_CONFIG_JSON/versions/latest:access"
    )
    assert captured_request["authorization"] == "Bearer adc-token"


def test_load_raises_when_adc_has_no_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_credentials = _FakeCredentials(refreshed_token="adc-token")

    def fake_default(
        scopes: list[str],
    ) -> tuple[_FakeCredentials, str | None]:
        assert scopes == [adapter_module._SECRET_MANAGER_SCOPE]
        return fake_credentials, None

    monkeypatch.setattr(
        "src.adapters.outbound.secret_manager.app_config_secret_loader_adapter.google_auth.default",
        fake_default,
    )

    loader = adapter_module.SecretManagerAppConfigLoaderAdapter()
    with pytest.raises(ValueError, match="No GCP project found in ADC"):
        loader.load()


def test_load_raises_when_secret_manager_returns_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_credentials = _FakeCredentials(refreshed_token="adc-token")

    def fake_default(
        scopes: list[str],
    ) -> tuple[_FakeCredentials, str]:
        assert scopes == [adapter_module._SECRET_MANAGER_SCOPE]
        return fake_credentials, "ai-agent-calendar-2603011621"

    def fake_get(
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        assert headers["Authorization"] == "Bearer adc-token"
        assert timeout == 10.0
        request = httpx.Request(method="GET", url=url)
        return httpx.Response(status_code=403, text="forbidden", request=request)

    monkeypatch.setattr(
        "src.adapters.outbound.secret_manager.app_config_secret_loader_adapter.google_auth.default",
        fake_default,
    )
    monkeypatch.setattr(
        "src.adapters.outbound.secret_manager.app_config_secret_loader_adapter.httpx.get",
        fake_get,
    )

    loader = adapter_module.SecretManagerAppConfigLoaderAdapter()
    with pytest.raises(ValueError, match="status code 403"):
        loader.load()
