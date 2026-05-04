"""Tests para DELETE /v1/dev/eval-runs/{run_id} — cascade delete de corrida.

Auth: requiere JWT de cualquier tenant logueado (NO el EVAL_ADMIN_SECRET).
El secret solo aplica a /v1/dev/eval-tenants (writes invasivos de tenants).
"""

import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.dev_router as dev_router
import src.services.dto.auth_dto as auth_dto
import src.services.dto.eval_run_cleanup_dto as eval_run_cleanup_dto
import src.services.exceptions as service_exceptions

_DELETE_STATS = eval_run_cleanup_dto.EvalRunDeleteStatsDTO(
    eval_runs_deleted=2,
    tenants_deleted=2,
)


def _make_claims() -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id="tenant-1",
        role="professional",
        exp=2_000_000_000,
        jti="jti-1",
        token_kind="access",
    )


def _make_client(
    *,
    delete_run_return: eval_run_cleanup_dto.EvalRunDeleteStatsDTO = _DELETE_STATS,
    delete_run_side_effect: Exception | None = None,
    authenticated: bool = True,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(dev_router.router)

    mock_cleanup_service = unittest.mock.MagicMock()
    if delete_run_side_effect is not None:
        mock_cleanup_service.delete_eval_run_cascade.side_effect = delete_run_side_effect
    else:
        mock_cleanup_service.delete_eval_run_cascade.return_value = delete_run_return

    mock_container = unittest.mock.MagicMock()
    mock_container.eval_run_cleanup_service = mock_cleanup_service

    def override_container() -> typing.Any:
        return mock_container

    app.dependency_overrides[http_dependencies.get_container] = override_container

    if authenticated:

        def override_claims() -> auth_dto.TokenClaimsDTO:
            return _make_claims()

        app.dependency_overrides[http_dependencies.get_current_claims] = override_claims
    else:

        def override_claims_unauth() -> auth_dto.TokenClaimsDTO:
            raise service_exceptions.AuthenticationError("missing or invalid token")

        app.dependency_overrides[http_dependencies.get_current_claims] = override_claims_unauth

    return fastapi.testclient.TestClient(app, raise_server_exceptions=False)


def test_delete_eval_run_with_valid_jwt_returns_200() -> None:
    client = _make_client()

    response = client.delete("/v1/dev/eval-runs/run-abc")

    assert response.status_code == 200
    body = response.json()
    assert body["eval_runs_deleted"] == 2
    assert body["tenants_deleted"] == 2


def test_delete_eval_run_without_jwt_returns_401() -> None:
    client = _make_client(authenticated=False)

    response = client.delete("/v1/dev/eval-runs/run-abc")

    assert response.status_code == 401


def test_delete_eval_run_calls_service_with_correct_run_id() -> None:
    client = _make_client()

    client.delete("/v1/dev/eval-runs/my-run-id")

    client.app.dependency_overrides[  # type: ignore[attr-defined]
        http_dependencies.get_container
    ]().eval_run_cleanup_service.delete_eval_run_cascade.assert_called_once_with("my-run-id")


def test_delete_eval_run_returns_zeros_when_no_docs() -> None:
    empty_stats = eval_run_cleanup_dto.EvalRunDeleteStatsDTO(
        eval_runs_deleted=0,
        tenants_deleted=0,
    )
    client = _make_client(delete_run_return=empty_stats)

    response = client.delete("/v1/dev/eval-runs/run-nonexistent")

    assert response.status_code == 200
    body = response.json()
    assert body["eval_runs_deleted"] == 0
    assert body["tenants_deleted"] == 0


def test_delete_eval_run_not_mounted_when_dev_disabled() -> None:
    """Con el router no incluido (dev disabled), el endpoint devuelve 404."""
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    client = fastapi.testclient.TestClient(app, raise_server_exceptions=False)

    response = client.delete("/v1/dev/eval-runs/run-abc")

    assert response.status_code == 404
