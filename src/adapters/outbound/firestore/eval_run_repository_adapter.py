import datetime

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore
import pydantic

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.eval_run as eval_run_entity
import src.ports.eval_run_repository_port as eval_run_repository_port


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt


def _normalize_datetime_fields(data: dict[str, object]) -> dict[str, object]:
    """Convert any naive datetime values returned by Firestore to UTC-aware."""
    result: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, datetime.datetime):
            result[key] = _ensure_utc(value)
        elif isinstance(value, list):
            result[key] = [
                _normalize_datetime_fields(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, dict):
            result[key] = _normalize_datetime_fields(value)
        else:
            result[key] = value
    return result


class FirestoreEvalRunRepositoryAdapter(eval_run_repository_port.EvalRunRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save_run(self, eval_run: eval_run_entity.EvalRun) -> None:
        doc_ref = self._client.document(firestore_paths.eval_run_document(eval_run.run_id))
        data = eval_run.model_dump(mode="json")
        try:
            doc_ref.set(data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save eval run in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save eval run in firestore"
            ) from error

    def save_conversation(
        self,
        run_id: str,
        conversation: eval_run_entity.EvalRunConversationSnapshot,
    ) -> None:
        doc_ref = self._client.document(
            firestore_paths.eval_run_conversation_document(run_id, conversation.persona_id)
        )
        data = conversation.model_dump(mode="json")
        try:
            doc_ref.set(data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save eval run conversation in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save eval run conversation in firestore"
            ) from error

    def list_runs(self, limit: int = 50) -> list[eval_run_entity.EvalRun]:
        collection_ref = self._client.collection(firestore_paths.EVAL_RUNS_COLLECTION)
        query = collection_ref.order_by(
            "started_at",
            direction=google_cloud_firestore.Query.DESCENDING,
        ).limit(limit)
        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list eval runs from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list eval runs from firestore"
            ) from error

        runs: list[eval_run_entity.EvalRun] = []
        for snapshot in snapshots:
            raw_data = snapshot.to_dict()
            if raw_data is None:
                continue
            normalized = _normalize_datetime_fields(raw_data)
            try:
                run = eval_run_entity.EvalRun.model_validate(normalized)
            except pydantic.ValidationError:
                continue
            runs.append(run)
        return runs

    def get_run(self, run_id: str) -> eval_run_entity.EvalRun | None:
        doc_ref = self._client.document(firestore_paths.eval_run_document(run_id))
        try:
            snapshot = doc_ref.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read eval run from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read eval run from firestore"
            ) from error
        if not snapshot.exists:
            return None
        raw_data = snapshot.to_dict()
        if raw_data is None:
            return None
        normalized = _normalize_datetime_fields(raw_data)
        return eval_run_entity.EvalRun.model_validate(normalized)

    def get_conversations(self, run_id: str) -> list[eval_run_entity.EvalRunConversationSnapshot]:
        collection_path = firestore_paths.eval_run_conversations_collection(run_id)
        collection_ref = self._client.collection(collection_path)
        query = collection_ref.order_by("persona_id")
        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list eval run conversations from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list eval run conversations from firestore"
            ) from error

        conversations: list[eval_run_entity.EvalRunConversationSnapshot] = []
        for snapshot in snapshots:
            raw_data = snapshot.to_dict()
            if raw_data is None:
                continue
            normalized = _normalize_datetime_fields(raw_data)
            try:
                conv = eval_run_entity.EvalRunConversationSnapshot.model_validate(normalized)
            except pydantic.ValidationError:
                continue
            conversations.append(conv)
        return conversations
