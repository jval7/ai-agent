import datetime

import src.adapters.outbound.inmemory.eval_run_repository_adapter as eval_run_repository_adapter
import src.domain.entities.eval_run as eval_run_entity

_NOW = datetime.datetime(2026, 4, 30, 12, 0, 0, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 4, 30, 13, 0, 0, tzinfo=datetime.UTC)
_EARLIER = datetime.datetime(2026, 4, 30, 11, 0, 0, tzinfo=datetime.UTC)


def _make_run(
    run_id: str,
    shape_name: str = "test_shape",
    started_at: datetime.datetime = _NOW,
    ok: int = 1,
    fail: int = 0,
) -> eval_run_entity.EvalRun:
    return eval_run_entity.EvalRun(
        run_id=run_id,
        shape_name=shape_name,
        started_at=started_at,
        total_personas=1,
        ok=ok,
        fail=fail,
        skipped=False,
    )


def _make_conversation(
    persona_id: str,
    status: str = "ok",
) -> eval_run_entity.EvalRunConversationSnapshot:
    return eval_run_entity.EvalRunConversationSnapshot(
        persona_id=persona_id,
        combos_satisfied=[["AGENDA_SIMPLE"]],
        status=status,  # type: ignore[arg-type]
        elapsed_seconds=1.5,
    )


def _make_repo() -> eval_run_repository_adapter.InMemoryEvalRunRepositoryAdapter:
    return eval_run_repository_adapter.InMemoryEvalRunRepositoryAdapter()


def test_save_run_and_get_run_round_trip() -> None:
    repo = _make_repo()
    run = _make_run("run-1")

    repo.save_run(run)
    retrieved = repo.get_run("run-1")

    assert retrieved is not None
    assert retrieved.run_id == "run-1"
    assert retrieved.shape_name == "test_shape"
    assert retrieved.ok == 1
    assert retrieved.fail == 0


def test_save_run_upserts_existing_run() -> None:
    repo = _make_repo()
    run = _make_run("run-1", ok=1)
    repo.save_run(run)

    updated_run = _make_run("run-1", ok=5)
    repo.save_run(updated_run)

    retrieved = repo.get_run("run-1")
    assert retrieved is not None
    assert retrieved.ok == 5


def test_get_run_returns_none_for_missing_run() -> None:
    repo = _make_repo()
    result = repo.get_run("nonexistent-run")
    assert result is None


def test_list_runs_ordered_by_started_at_desc() -> None:
    repo = _make_repo()
    run_a = _make_run("run-a", started_at=_EARLIER)
    run_b = _make_run("run-b", started_at=_NOW)
    run_c = _make_run("run-c", started_at=_LATER)

    repo.save_run(run_a)
    repo.save_run(run_b)
    repo.save_run(run_c)

    runs = repo.list_runs()

    assert len(runs) == 3
    assert runs[0].run_id == "run-c"
    assert runs[1].run_id == "run-b"
    assert runs[2].run_id == "run-a"


def test_list_runs_respects_limit() -> None:
    repo = _make_repo()
    repo.save_run(_make_run("run-1", started_at=_EARLIER))
    repo.save_run(_make_run("run-2", started_at=_NOW))
    repo.save_run(_make_run("run-3", started_at=_LATER))

    runs = repo.list_runs(limit=2)

    assert len(runs) == 2
    assert runs[0].run_id == "run-3"
    assert runs[1].run_id == "run-2"


def test_list_runs_returns_empty_when_no_runs() -> None:
    repo = _make_repo()
    runs = repo.list_runs()
    assert runs == []


def test_save_conversation_and_get_conversations_round_trip() -> None:
    repo = _make_repo()
    run = _make_run("run-1")
    repo.save_run(run)

    conv = _make_conversation("persona-abc", status="ok")
    repo.save_conversation("run-1", conv)

    conversations = repo.get_conversations("run-1")

    assert len(conversations) == 1
    assert conversations[0].persona_id == "persona-abc"
    assert conversations[0].status == "ok"
    assert conversations[0].elapsed_seconds == 1.5


def test_get_conversations_ordered_by_persona_id_asc() -> None:
    repo = _make_repo()
    repo.save_run(_make_run("run-1"))

    repo.save_conversation("run-1", _make_conversation("persona-z"))
    repo.save_conversation("run-1", _make_conversation("persona-a"))
    repo.save_conversation("run-1", _make_conversation("persona-m"))

    conversations = repo.get_conversations("run-1")

    assert len(conversations) == 3
    assert conversations[0].persona_id == "persona-a"
    assert conversations[1].persona_id == "persona-m"
    assert conversations[2].persona_id == "persona-z"


def test_get_conversations_returns_empty_for_missing_run() -> None:
    repo = _make_repo()
    conversations = repo.get_conversations("nonexistent-run")
    assert conversations == []


def test_save_conversation_upserts_by_persona_id() -> None:
    repo = _make_repo()
    repo.save_run(_make_run("run-1"))

    conv_ok = _make_conversation("persona-1", status="ok")
    repo.save_conversation("run-1", conv_ok)

    conv_fail = _make_conversation("persona-1", status="fail")
    repo.save_conversation("run-1", conv_fail)

    conversations = repo.get_conversations("run-1")
    assert len(conversations) == 1
    assert conversations[0].status == "fail"


def test_conversations_are_isolated_per_run() -> None:
    repo = _make_repo()
    repo.save_run(_make_run("run-1"))
    repo.save_run(_make_run("run-2"))

    repo.save_conversation("run-1", _make_conversation("persona-a"))
    repo.save_conversation("run-2", _make_conversation("persona-b"))

    convs_run1 = repo.get_conversations("run-1")
    convs_run2 = repo.get_conversations("run-2")

    assert len(convs_run1) == 1
    assert convs_run1[0].persona_id == "persona-a"

    assert len(convs_run2) == 1
    assert convs_run2[0].persona_id == "persona-b"
