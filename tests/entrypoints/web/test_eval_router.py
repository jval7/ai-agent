"""Tests para eval_router (Fase 5).

Se monta el router directamente en una FastAPI de prueba, sobreescribiendo
el container con un mock — sin tocar el contenedor real ni Firestore.
"""

import datetime
import typing
import unittest.mock

import fastapi
import fastapi.testclient

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.eval_router as eval_router
import src.services.dto.eval_dto as eval_dto

_CAPABILITY_DOC = eval_dto.EvalCapabilityDocDTO(
    id="asks_about_price",
    description="el paciente pregunta cuánto vale la consulta o servicio",
    implications="exigirá que el bot cotice antes de pedir datos personales",
    category="behavior",
)

_NOW = datetime.datetime(2026, 4, 30, 12, 0, 0, tzinfo=datetime.UTC)

_SHAPE_DTO = eval_dto.ShapeDTO(
    name="shape_minimal",
    description="Smoke test",
    required_combos=[["new_patient"]],
    rendered_system_prompt="<base_system_prompt>...</base_system_prompt>",
)

_PERSONA_DTO = eval_dto.PersonaDTO(
    id="diego_local_asks_price",
    display_name="Diego Hernandez",
    capabilities=["local_patient", "new_patient", "asks_about_price"],
    profile_group="psicologa",
)

_PROMPT_VERSION_DTO = eval_dto.PromptVersionDTO(
    id="current",
    label="Versión actual",
    active=True,
)

_RUN_LIST_ITEM = eval_dto.EvalRunListItemDTO(
    run_doc_id="abc123_shape_minimal",
    run_id="abc123",
    shape_name="shape_minimal",
    started_at=_NOW,
    finished_at=None,
    total_personas=1,
    ok=1,
    fail=0,
    skipped=False,
)

_RUN_DETAIL = eval_dto.EvalRunDetailDTO(
    run_doc_id="abc123_shape_minimal",
    run_id="abc123",
    shape_name="shape_minimal",
    prompt_version_id=None,
    started_at=_NOW,
    finished_at=None,
    total_personas=1,
    ok=1,
    fail=0,
    skipped=False,
    uncovered_combos=[],
    eval_tenant_id=None,
    conversations=[
        eval_dto.EvalRunConversationSnapshotDTO(
            persona_id="diego_local_asks_price",
            combos_satisfied=[["new_patient"]],
            status="ok",
            elapsed_seconds=5.0,
            transcript=[],
        )
    ],
)


def _make_client(
    *,
    list_shapes_return: list[eval_dto.ShapeDTO] | None = None,
    list_personas_return: list[eval_dto.PersonaDTO] | None = None,
    list_prompt_versions_return: list[eval_dto.PromptVersionDTO] | None = None,
    list_runs_return: list[eval_dto.EvalRunListItemDTO] | None = None,
    get_run_return: eval_dto.EvalRunDetailDTO | None = _RUN_DETAIL,
    list_capabilities_return: list[eval_dto.EvalCapabilityDocDTO] | None = None,
) -> fastapi.testclient.TestClient:
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    app.include_router(eval_router.router)

    mock_service = unittest.mock.MagicMock()
    mock_service.list_shapes.return_value = (
        list_shapes_return if list_shapes_return is not None else [_SHAPE_DTO]
    )
    mock_service.list_personas.return_value = (
        list_personas_return if list_personas_return is not None else [_PERSONA_DTO]
    )
    mock_service.list_prompt_versions.return_value = (
        list_prompt_versions_return
        if list_prompt_versions_return is not None
        else [_PROMPT_VERSION_DTO]
    )
    mock_service.list_runs.return_value = (
        list_runs_return if list_runs_return is not None else [_RUN_LIST_ITEM]
    )
    mock_service.get_run.return_value = get_run_return
    mock_service.list_capabilities.return_value = (
        list_capabilities_return if list_capabilities_return is not None else [_CAPABILITY_DOC]
    )

    mock_container = unittest.mock.MagicMock()
    mock_container.eval_query_service = mock_service

    def override_container() -> typing.Any:
        return mock_container

    app.dependency_overrides[http_dependencies.get_container] = override_container
    return fastapi.testclient.TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /v1/eval/shapes
# ---------------------------------------------------------------------------


def test_list_shapes_returns_200() -> None:
    client = _make_client()
    response = client.get("/v1/eval/shapes")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "shape_minimal"
    assert body["items"][0]["rendered_system_prompt"]


def test_list_shapes_returns_empty_items() -> None:
    client = _make_client(list_shapes_return=[])
    response = client.get("/v1/eval/shapes")
    assert response.status_code == 200
    assert response.json()["items"] == []


# ---------------------------------------------------------------------------
# GET /v1/eval/personas
# ---------------------------------------------------------------------------


def test_list_personas_returns_200() -> None:
    client = _make_client()
    response = client.get("/v1/eval/personas")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "diego_local_asks_price"
    assert body["items"][0]["profile_group"] == "psicologa"


# ---------------------------------------------------------------------------
# GET /v1/eval/prompt-versions
# ---------------------------------------------------------------------------


def test_list_prompt_versions_returns_placeholder() -> None:
    client = _make_client()
    response = client.get("/v1/eval/prompt-versions")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "current"
    assert body["items"][0]["active"] is True


# ---------------------------------------------------------------------------
# GET /v1/eval/runs
# ---------------------------------------------------------------------------


def test_list_runs_returns_200() -> None:
    client = _make_client()
    response = client.get("/v1/eval/runs")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["run_doc_id"] == "abc123_shape_minimal"
    assert body["items"][0]["run_id"] == "abc123"


def test_list_runs_accepts_limit_param() -> None:
    client = _make_client()
    response = client.get("/v1/eval/runs?limit=10")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /v1/eval/runs/{run_doc_id}
# ---------------------------------------------------------------------------


def test_get_run_returns_detail_with_conversations() -> None:
    client = _make_client()
    response = client.get("/v1/eval/runs/abc123_shape_minimal")
    assert response.status_code == 200
    body = response.json()
    assert body["run_doc_id"] == "abc123_shape_minimal"
    assert len(body["conversations"]) == 1
    assert body["conversations"][0]["persona_id"] == "diego_local_asks_price"


def test_get_run_returns_404_when_missing() -> None:
    client = _make_client(get_run_return=None)
    response = client.get("/v1/eval/runs/nonexistent_run")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Env gate: sin router → 404
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /v1/eval/capabilities
# ---------------------------------------------------------------------------


def test_list_capabilities_returns_200() -> None:
    client = _make_client()
    response = client.get("/v1/eval/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "asks_about_price"
    assert body["items"][0]["category"] == "behavior"


def test_list_capabilities_returns_empty_items() -> None:
    client = _make_client(list_capabilities_return=[])
    response = client.get("/v1/eval/capabilities")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_capabilities_item_has_all_fields() -> None:
    client = _make_client()
    response = client.get("/v1/eval/capabilities")
    item = response.json()["items"][0]
    assert "id" in item
    assert "description" in item
    assert "implications" in item
    assert "category" in item


# ---------------------------------------------------------------------------
# Env gate: sin router → 404
# ---------------------------------------------------------------------------


def test_endpoints_are_excluded_when_eval_disabled() -> None:
    """Con eval_endpoints_enabled=False el router no se monta y todos los
    endpoints devuelven 404 — mismo patrón que test_dev_router_eval_tenants."""
    app = fastapi.FastAPI()
    http_exception_handlers.register_exception_handlers(app)
    # El router NO se incluye (simulando main.py con eval_endpoints_enabled=False)
    client = fastapi.testclient.TestClient(app, raise_server_exceptions=False)

    assert client.get("/v1/eval/shapes").status_code == 404
    assert client.get("/v1/eval/personas").status_code == 404
    assert client.get("/v1/eval/prompt-versions").status_code == 404
    assert client.get("/v1/eval/runs").status_code == 404
    assert client.get("/v1/eval/runs/any-id").status_code == 404
    assert client.get("/v1/eval/capabilities").status_code == 404
