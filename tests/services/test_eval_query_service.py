"""Tests para EvalQueryService (Fase 5).

Todos los tests usan el InMemoryEvalRunRepositoryAdapter y el directorio de
fixtures reales (tests/fixtures/profiles/) para evitar dependencias externas.
"""

import datetime
import pathlib

import src.adapters.outbound.inmemory.eval_run_repository_adapter as inmemory_eval_repo
import src.domain.entities.eval_run as eval_run_entity
import src.services.use_cases.eval_query_service as eval_query_service

_FIXTURES_DIR = pathlib.Path("tests/fixtures/profiles")
_NOW = datetime.datetime(2026, 4, 30, 12, 0, 0, tzinfo=datetime.UTC)


def _make_service(
    fixtures_dir: pathlib.Path = _FIXTURES_DIR,
) -> tuple[
    eval_query_service.EvalQueryService, inmemory_eval_repo.InMemoryEvalRunRepositoryAdapter
]:
    repo = inmemory_eval_repo.InMemoryEvalRunRepositoryAdapter()
    svc = eval_query_service.EvalQueryService(
        eval_run_repository=repo,
        shapes_directory=fixtures_dir,
    )
    return svc, repo


def _make_run(
    run_id: str,
    shape_name: str = "shape_minimal",
    started_at: datetime.datetime = _NOW,
    ok: int = 1,
    fail: int = 0,
    skipped: bool = False,
) -> eval_run_entity.EvalRun:
    return eval_run_entity.EvalRun(
        run_id=run_id,
        shape_name=shape_name,
        started_at=started_at,
        total_personas=ok + fail,
        ok=ok,
        fail=fail,
        skipped=skipped,
    )


def _make_conversation(
    persona_id: str,
    status: str = "ok",
) -> eval_run_entity.EvalRunConversationSnapshot:
    return eval_run_entity.EvalRunConversationSnapshot(
        persona_id=persona_id,
        combos_satisfied=[["new_patient"]],
        status=status,  # type: ignore[arg-type]
        elapsed_seconds=5.0,
    )


# ---------------------------------------------------------------------------
# list_shapes
# ---------------------------------------------------------------------------


def test_list_shapes_renders_system_prompt() -> None:
    """Cada shape DTO tiene rendered_system_prompt no vacío."""
    svc, _ = _make_service()
    shapes = svc.list_shapes()
    assert len(shapes) > 0
    for shape in shapes:
        assert shape.rendered_system_prompt, (
            f"rendered_system_prompt vacío para shape {shape.name!r}"
        )
        assert "<base_system_prompt>" in shape.rendered_system_prompt


def test_list_shapes_has_name_description_and_combos() -> None:
    svc, _ = _make_service()
    shapes = svc.list_shapes()
    for shape in shapes:
        assert shape.name
        assert shape.description
        assert isinstance(shape.required_combos, list)
        for combo in shape.required_combos:
            assert isinstance(combo, list)
            assert all(isinstance(cap, str) for cap in combo)


def test_list_shapes_loads_all_fixtures() -> None:
    svc, _ = _make_service()
    shapes = svc.list_shapes()
    names = {s.name for s in shapes}
    assert "shape_minimal" in names
    assert "shape_multicurrency" in names


# ---------------------------------------------------------------------------
# list_personas
# ---------------------------------------------------------------------------


def test_list_personas_groups_by_psicologa_or_ortodoncista() -> None:
    """Cada persona tiene profile_group 'psicologa' o 'ortodoncista'."""
    svc, _ = _make_service()
    personas = svc.list_personas()
    for persona in personas:
        assert persona.profile_group in {"psicologa", "ortodoncista"}, (
            f"profile_group inesperado: {persona.profile_group!r}"
        )


def test_list_personas_has_required_fields() -> None:
    svc, _ = _make_service()
    personas = svc.list_personas()
    for persona in personas:
        assert persona.id
        assert persona.display_name
        assert isinstance(persona.capabilities, list)


# ---------------------------------------------------------------------------
# list_prompt_versions
# ---------------------------------------------------------------------------


def test_list_prompt_versions_returns_placeholder() -> None:
    svc, _ = _make_service()
    versions = svc.list_prompt_versions()
    assert len(versions) == 1
    assert versions[0].id == "current"
    assert versions[0].label == "Versión actual"
    assert versions[0].active is True


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------


def test_list_runs_returns_dto_with_doc_id() -> None:
    """run_doc_id debe ser '{run_id}_{shape_name}'."""
    svc, repo = _make_service()
    run = _make_run(run_id="abc123", shape_name="shape_minimal")
    repo.save_run(run)

    items = svc.list_runs()

    assert len(items) == 1
    assert items[0].run_doc_id == "abc123_shape_minimal"
    assert items[0].run_id == "abc123"
    assert items[0].shape_name == "shape_minimal"


def test_list_runs_returns_empty_when_no_runs() -> None:
    svc, _ = _make_service()
    items = svc.list_runs()
    assert items == []


def test_list_runs_respects_limit() -> None:
    svc, repo = _make_service()
    for i in range(5):
        repo.save_run(_make_run(run_id=f"run-{i}", shape_name="shape_minimal"))
    items = svc.list_runs(limit=3)
    assert len(items) == 3


# ---------------------------------------------------------------------------
# get_run
# ---------------------------------------------------------------------------


def test_get_run_returns_detail_with_conversations() -> None:
    """get_run debe incluir la lista de conversaciones."""
    svc, repo = _make_service()
    run = _make_run(run_id="run-x", shape_name="shape_minimal")
    repo.save_run(run)

    # El adapter in-memory usa run_id como doc_id — consistente con Opción C.
    conv = _make_conversation("diego_local_asks_price", status="ok")
    repo.save_conversation("run-x", conv)

    detail = svc.get_run("run-x")

    assert detail is not None
    assert detail.run_doc_id == "run-x_shape_minimal"
    assert detail.run_id == "run-x"
    assert len(detail.conversations) == 1
    assert detail.conversations[0].persona_id == "diego_local_asks_price"
    assert detail.conversations[0].status == "ok"


def test_get_run_returns_none_for_missing_run_id() -> None:
    svc, _ = _make_service()
    result = svc.get_run("nonexistent-run-id")
    assert result is None


def test_get_run_conversations_have_transcript_field() -> None:
    svc, repo = _make_service()
    run = _make_run(run_id="run-y")
    repo.save_run(run)
    conv = _make_conversation("persona-1")
    repo.save_conversation("run-y", conv)

    detail = svc.get_run("run-y")
    assert detail is not None
    assert detail.conversations[0].transcript == []
