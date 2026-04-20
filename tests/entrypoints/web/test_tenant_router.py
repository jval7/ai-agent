import datetime
import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.domain.entities.tenant as tenant_entity
import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.tenant_router as tenant_router
import src.services.dto.auth_dto as auth_dto
import src.services.use_cases.tenant_profile_service as tenant_profile_service
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

_PROFESSIONAL_CLAIMS = auth_dto.TokenClaimsDTO(
    sub="user-1",
    tenant_id="tenant-1",
    role="professional",
    exp=2000000000,
    jti="jti-1",
    token_kind="access",
)


def _make_service(
    professional_name: str | None = None,
) -> tenant_profile_service.TenantProfileService:
    repo = fake_adapters.FakeTenantRepository()
    repo.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Clinic",
            created_at=_NOW,
            updated_at=_NOW,
            professional_name=professional_name,
        )
    )
    clock = fake_adapters.FixedClock(_NOW)
    return tenant_profile_service.TenantProfileService(
        tenant_repository=repo,
        clock=clock,
    )


def _make_client(
    service: tenant_profile_service.TenantProfileService,
    claims: auth_dto.TokenClaimsDTO = _PROFESSIONAL_CLAIMS,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(tenant_router.router)

    mock_container = unittest.mock.MagicMock()
    mock_container.tenant_profile_service = service

    def override_container() -> typing.Any:
        return mock_container

    def override_claims() -> auth_dto.TokenClaimsDTO:
        return claims

    app.dependency_overrides[http_dependencies.get_container] = override_container
    app.dependency_overrides[http_dependencies.get_current_claims] = override_claims
    return fastapi.testclient.TestClient(app, raise_server_exceptions=True)


def test_get_profile_returns_dto() -> None:
    service = _make_service(professional_name="Dr. Ana García")
    client = _make_client(service)

    response = client.get("/v1/tenant/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant-1"
    assert body["professional_name"] == "Dr. Ana García"


def test_get_profile_returns_null_professional_name_when_not_set() -> None:
    service = _make_service(professional_name=None)
    client = _make_client(service)

    response = client.get("/v1/tenant/profile")

    assert response.status_code == 200
    assert response.json()["professional_name"] is None


def test_put_profile_updates_professional_name() -> None:
    service = _make_service()
    client = _make_client(service)

    response = client.put(
        "/v1/tenant/profile",
        json={"professional_name": "Dr. Jhon Valderrama"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["professional_name"] == "Dr. Jhon Valderrama"


def test_put_profile_clears_professional_name_when_null() -> None:
    service = _make_service(professional_name="Old Name")
    client = _make_client(service)

    response = client.put(
        "/v1/tenant/profile",
        json={"professional_name": None},
    )

    assert response.status_code == 200
    assert response.json()["professional_name"] is None


def test_get_profile_returns_403_for_non_professional() -> None:
    service = _make_service()
    non_pro_claims = auth_dto.TokenClaimsDTO(
        sub="user-2",
        tenant_id="tenant-1",
        role="admin",
        exp=2000000000,
        jti="jti-2",
        token_kind="access",
    )
    client = _make_client(service, claims=non_pro_claims)

    response = client.get("/v1/tenant/profile")

    assert response.status_code == 403


def test_put_profile_returns_403_for_non_professional() -> None:
    service = _make_service()
    non_pro_claims = auth_dto.TokenClaimsDTO(
        sub="user-2",
        tenant_id="tenant-1",
        role="admin",
        exp=2000000000,
        jti="jti-2",
        token_kind="access",
    )
    client = _make_client(service, claims=non_pro_claims)

    response = client.put(
        "/v1/tenant/profile",
        json={"professional_name": "Dr. X"},
    )

    assert response.status_code == 403
