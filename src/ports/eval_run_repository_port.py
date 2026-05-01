import abc

import src.domain.entities.eval_run as eval_run_entity


class EvalRunRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save_run(self, eval_run: eval_run_entity.EvalRun) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def save_conversation(
        self,
        run_id: str,
        conversation: eval_run_entity.EvalRunConversationSnapshot,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_runs(self, limit: int = 50) -> list[eval_run_entity.EvalRun]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_run(self, run_id: str) -> eval_run_entity.EvalRun | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_conversations(self, run_id: str) -> list[eval_run_entity.EvalRunConversationSnapshot]:
        raise NotImplementedError
