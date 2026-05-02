"""Tests para DELETE /v1/dev/eval-runs/{run_id} — cascade delete de corrida."""

import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.dev_router as dev_router
import src.infra.settings as app_settings
import src.services.dto.eval_run_cleanup_dto as eval_run_cleanup_dto

_VALID_SECRET = "super-secret-eval"
_DELETE_STATS = eval_run_cleanup_dto.EvalRunDeleteStatsDTO(
    eval_runs_deleted=2,
    tenants_deleted=2,
)


def _make_client(
    *,
    eval_admin_secret: str | None = _VALID_SECRET,
    delete_run_return: eval_run_cleanup_dto.EvalRunDeleteStatsDTO = _DELETE_STATS,
    delete_run_side_effect: Exception | None = None,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(dev_router.router)

    mock_settings = unittest.mock.MagicMock(spec=app_settings.Settings)
    mock_settings.eval_admin_secret = eval_admin_secret
    mock_settings.enable_dev_endpoints = True

    mock_cleanup_service = unittest.mock.MagicMock()
    if delete_run_side_effect is not None:
        mock_cleanup_service.delete_eval_run_cascade.side_effect = delete_run_side_effect
    else:
        mock_cleanup_service.delete_eval_run_cascade.return_value = delete_run_return

    mock_container = unittest.mock.MagicMock()
    mock_container.settings = mock_settings
    mock_container.eval_run_cleanup_service = mock_cleanup_service

    def override_container() -> typing.Any:
        return mock_container

    app.dependency_overrides[http_dependencies.get_container] = override_container
    return fastapi.testclient.TestClient(app, raise_server_exceptions=False)


def test_delete_eval_run_with_correct_secret_returns_200() -> None:
    client = _make_client()

    response = client.delete(
        "/v1/dev/eval-runs/run-abc",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eval_runs_deleted"] == 2
    assert body["tenants_deleted"] == 2


def test_delete_eval_run_with_wrong_secret_returns_401() -> None:
    client = _make_client()

    response = client.delete(
        "/v1/dev/eval-runs/run-abc",
        headers={"X-Eval-Admin-Secret": "wrong-secret"},
    )

    assert response.status_code == 401


def test_delete_eval_run_without_header_returns_401() -> None:
    client = _make_client()

    response = client.delete("/v1/dev/eval-runs/run-abc")

    assert response.status_code == 401


def test_delete_eval_run_when_secret_not_configured_returns_401() -> None:
    client = _make_client(eval_admin_secret=None)

    response = client.delete(
        "/v1/dev/eval-runs/run-abc",
        headers={"X-Eval-Admin-Secret": "any-secret"},
    )

    assert response.status_code == 401


def test_delete_eval_run_calls_service_with_correct_run_id() -> None:
    client = _make_client()

    client.delete(
        "/v1/dev/eval-runs/my-run-id",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    client.app.dependency_overrides[  # type: ignore[attr-defined]
        http_dependencies.get_container
    ]().eval_run_cleanup_service.delete_eval_run_cascade.assert_called_once_with("my-run-id")


def test_delete_eval_run_returns_zeros_when_no_docs() -> None:
    empty_stats = eval_run_cleanup_dto.EvalRunDeleteStatsDTO(
        eval_runs_deleted=0,
        tenants_deleted=0,
    )
    client = _make_client(delete_run_return=empty_stats)

    response = client.delete(
        "/v1/dev/eval-runs/run-nonexistent",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eval_runs_deleted"] == 0
    assert body["tenants_deleted"] == 0


def test_delete_eval_run_not_mounted_when_dev_disabled() -> None:
    """Con el router no incluido (dev disabled), el endpoint devuelve 404."""
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    client = fastapi.testclient.TestClient(app, raise_server_exceptions=False)

    response = client.delete(
        "/v1/dev/eval-runs/run-abc",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 404
