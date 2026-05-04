import src.domain.entities.eval_run as eval_run_entity
import src.ports.eval_run_repository_port as eval_run_repository_port


class InMemoryEvalRunRepositoryAdapter(eval_run_repository_port.EvalRunRepositoryPort):
    def __init__(self) -> None:
        # Key: run_doc_id = "{run_id}_{shape_name}"
        self._runs: dict[str, eval_run_entity.EvalRun] = {}
        # Key: run_doc_id → {persona_id → snapshot}
        self._conversations: dict[str, dict[str, eval_run_entity.EvalRunConversationSnapshot]] = {}

    def _run_doc_id(self, run: eval_run_entity.EvalRun) -> str:
        return f"{run.run_id}_{run.shape_name}"

    def save_run(self, eval_run: eval_run_entity.EvalRun) -> None:
        doc_id = self._run_doc_id(eval_run)
        self._runs[doc_id] = eval_run.model_copy(deep=True)

    def save_conversation(
        self,
        run_id: str,
        conversation: eval_run_entity.EvalRunConversationSnapshot,
    ) -> None:
        if run_id not in self._conversations:
            self._conversations[run_id] = {}
        self._conversations[run_id][conversation.persona_id] = conversation.model_copy(deep=True)

    def list_runs(self, limit: int = 50) -> list[eval_run_entity.EvalRun]:
        sorted_runs = sorted(
            self._runs.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )
        return [r.model_copy(deep=True) for r in sorted_runs[:limit]]

    def get_run(self, run_id: str) -> eval_run_entity.EvalRun | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        return run.model_copy(deep=True)

    def get_conversations(self, run_id: str) -> list[eval_run_entity.EvalRunConversationSnapshot]:
        run_convs = self._conversations.get(run_id, {})
        sorted_convs = sorted(run_convs.values(), key=lambda c: c.persona_id)
        return [c.model_copy(deep=True) for c in sorted_convs]

    def list_runs_by_run_id(self, run_id: str) -> list[eval_run_entity.EvalRun]:
        return [r.model_copy(deep=True) for r in self._runs.values() if r.run_id == run_id]

    def delete_run(self, run_doc_id: str) -> None:
        self._runs.pop(run_doc_id, None)
        self._conversations.pop(run_doc_id, None)
