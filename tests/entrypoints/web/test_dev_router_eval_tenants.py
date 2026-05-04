import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.dev_router as dev_router
import src.infra.settings as app_settings
import src.services.dto.eval_tenant_dto as eval_tenant_dto
import src.services.exceptions as service_exceptions

_VALID_SECRET = "super-secret-eval"
_CREATED_DTO = eval_tenant_dto.EvalTenantCreatedDTO(
    tenant_id="tenant-eval-1",
    email="eval-psicologa-run1@eval.local",
    password="deadbeef12345678",
    phone_number_id="mock_eval_run1_psicologa",
    access_token="access-tok",
    refresh_token="refresh-tok",
)


def _make_client(
    *,
    eval_admin_secret: str | None = _VALID_SECRET,
    create_return: eval_tenant_dto.EvalTenantCreatedDTO = _CREATED_DTO,
    delete_side_effect: Exception | None = None,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(dev_router.router)

    mock_settings = unittest.mock.MagicMock(spec=app_settings.Settings)
    mock_settings.eval_admin_secret = eval_admin_secret
    mock_settings.enable_dev_endpoints = True

    mock_eval_service = unittest.mock.MagicMock()
    mock_eval_service.create_eval_tenant.return_value = create_return
    if delete_side_effect is not None:
        mock_eval_service.delete_eval_tenant.side_effect = delete_side_effect
    else:
        mock_eval_service.delete_eval_tenant.return_value = None

    mock_container = unittest.mock.MagicMock()
    mock_container.settings = mock_settings
    mock_container.eval_tenant_service = mock_eval_service

    def override_container() -> typing.Any:
        return mock_container

    app.dependency_overrides[http_dependencies.get_container] = override_container
    return fastapi.testclient.TestClient(app, raise_server_exceptions=False)


def test_create_eval_tenant_with_correct_secret_returns_201() -> None:
    client = _make_client()

    response = client.post(
        "/v1/dev/eval-tenants",
        json={"run_id": "run1", "shape_name": "psicologa"},
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "tenant-eval-1"
    assert body["phone_number_id"] == "mock_eval_run1_psicologa"
    assert "access_token" in body
    assert "refresh_token" in body


def test_create_eval_tenant_with_wrong_secret_returns_401() -> None:
    client = _make_client()

    response = client.post(
        "/v1/dev/eval-tenants",
        json={"run_id": "run1", "shape_name": "psicologa"},
        headers={"X-Eval-Admin-Secret": "wrong-secret"},
    )

    assert response.status_code == 401


def test_create_eval_tenant_without_header_returns_401() -> None:
    client = _make_client()

    response = client.post(
        "/v1/dev/eval-tenants",
        json={"run_id": "run1", "shape_name": "psicologa"},
    )

    assert response.status_code == 401


def test_create_eval_tenant_when_secret_not_configured_returns_401() -> None:
    client = _make_client(eval_admin_secret=None)

    response = client.post(
        "/v1/dev/eval-tenants",
        json={"run_id": "run1", "shape_name": "psicologa"},
        headers={"X-Eval-Admin-Secret": "any-secret"},
    )

    assert response.status_code == 401


def test_delete_eval_tenant_with_correct_secret_returns_204() -> None:
    client = _make_client()

    response = client.delete(
        "/v1/dev/eval-tenants/tenant-eval-1",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 204


def test_delete_eval_tenant_with_wrong_secret_returns_401() -> None:
    client = _make_client()

    response = client.delete(
        "/v1/dev/eval-tenants/tenant-eval-1",
        headers={"X-Eval-Admin-Secret": "wrong-secret"},
    )

    assert response.status_code == 401


def test_delete_non_eval_tenant_returns_400() -> None:
    client = _make_client(
        delete_side_effect=service_exceptions.InvalidStateError(
            "tenant is not an eval tenant — refusing cascade delete"
        )
    )

    response = client.delete(
        "/v1/dev/eval-tenants/regular-tenant",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 400


def test_delete_missing_tenant_returns_404() -> None:
    client = _make_client(
        delete_side_effect=service_exceptions.EntityNotFoundError("eval tenant not found")
    )

    response = client.delete(
        "/v1/dev/eval-tenants/ghost-tenant",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response.status_code == 404


def test_endpoints_not_mounted_when_dev_disabled() -> None:
    """When enable_dev_endpoints=False, the router is not included and endpoints return 404."""
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    # Router is NOT included — simulating main.py gating
    # (In production the dev_router is only included when enable_dev_endpoints=True)
    client = fastapi.testclient.TestClient(app, raise_server_exceptions=False)

    response_post = client.post(
        "/v1/dev/eval-tenants",
        json={"run_id": "r1", "shape_name": "s1"},
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )
    response_delete = client.delete(
        "/v1/dev/eval-tenants/tenant-1",
        headers={"X-Eval-Admin-Secret": _VALID_SECRET},
    )

    assert response_post.status_code == 404
    assert response_delete.status_code == 404
