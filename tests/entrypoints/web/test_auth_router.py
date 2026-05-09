"""Tests for the /v1/auth endpoints — focusing on /me edge cases."""

import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.auth_router as auth_router
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto

_CLAIMS = auth_dto.TokenClaimsDTO(
    sub="user-123",
    tenant_id="tenant-456",
    role=service_constants.ROLE_PROFESSIONAL,
    exp=9999999999,
    jti="jti-xyz",
    token_kind="access",
)


def _make_client(
    claims: auth_dto.TokenClaimsDTO = _CLAIMS,
    mock_container: unittest.mock.MagicMock | None = None,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(auth_router.router)

    container = mock_container or unittest.mock.MagicMock()

    def override_container() -> typing.Any:
        return container

    def override_claims() -> auth_dto.TokenClaimsDTO:
        return claims

    app.dependency_overrides[http_dependencies.get_container] = override_container
    app.dependency_overrides[http_dependencies.get_current_claims] = override_claims
    return fastapi.testclient.TestClient(app, raise_server_exceptions=False)


def test_get_me_returns_user_info_when_user_exists() -> None:
    container = unittest.mock.MagicMock()
    fake_user = unittest.mock.MagicMock()
    fake_user.email = "real@example.com"
    container.auth_service.get_user_by_id.return_value = fake_user

    client = _make_client(mock_container=container)
    response = client.get("/v1/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "real@example.com"
    assert data["user_id"] == _CLAIMS.sub
    assert data["role"] == _CLAIMS.role
    assert data["tenant_id"] == _CLAIMS.tenant_id


def test_get_me_returns_404_when_user_not_found() -> None:
    """Valid token but user record missing → 404, not a fallback to claims.sub."""
    container = unittest.mock.MagicMock()
    container.auth_service.get_user_by_id.return_value = None

    client = _make_client(mock_container=container)
    response = client.get("/v1/auth/me")

    assert response.status_code == 404
    # The response body must NOT expose the user_id as an email
    body = response.json()
    assert "user not found" in body.get("detail", "")
