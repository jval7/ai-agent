import datetime
import json

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore
import pydantic

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.eval_run as eval_run_entity
import src.infra.logs as app_logs
import src.ports.eval_run_repository_port as eval_run_repository_port

logger = app_logs.get_logger(__name__)


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


def _unflatten_nested_arrays(data: dict[str, object], keys: list[str]) -> dict[str, object]:
    """Inverso de `_flatten_nested_arrays` (en scripts/load_test.py): reconstruye
    `list[list[X]]` desde la representacion plana `list[str]` JSON-encoded
    que se guardo en Firestore (que no permite arrays anidados).

    Tolera registros viejos guardados antes del flatten — si los items ya
    son listas (no strings), los devuelve tal cual.
    """
    result = dict(data)
    for key in keys:
        value = result.get(key)
        if isinstance(value, list):
            unflattened: list[object] = []
            for item in value:
                if isinstance(item, str):
                    try:
                        unflattened.append(json.loads(item))
                    except json.JSONDecodeError:
                        logger.warning(
                            "eval_run_repository: skipping malformed JSON item in field %s: %r",
                            key,
                            item,
                        )
                else:
                    unflattened.append(item)
            result[key] = unflattened
    return result


def _decode_run_doc(raw_data: dict[str, object]) -> dict[str, object]:
    normalized = _normalize_datetime_fields(raw_data)
    return _unflatten_nested_arrays(normalized, ["uncovered_combos"])


def _decode_conversation_doc(raw_data: dict[str, object]) -> dict[str, object]:
    normalized = _normalize_datetime_fields(raw_data)
    return _unflatten_nested_arrays(normalized, ["combos_satisfied"])


def _flatten_for_firestore(data: dict[str, object], keys: list[str]) -> dict[str, object]:
    """Mismo aplanado que `scripts/load_test._flatten_nested_arrays`. Lo
    duplicamos aca para que el adapter sea consistente cuando se invoque
    desde el backend (ej. tests o uso programatico futuro).
    """
    out = dict(data)
    for key in keys:
        value = out.get(key)
        if isinstance(value, list):
            out[key] = [json.dumps(item) if isinstance(item, list) else item for item in value]
    return out


class FirestoreEvalRunRepositoryAdapter(eval_run_repository_port.EvalRunRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save_run(self, eval_run: eval_run_entity.EvalRun) -> None:
        run_doc_id = f"{eval_run.run_id}_{eval_run.shape_name}"
        doc_ref = self._client.document(firestore_paths.eval_run_document(run_doc_id))
        data = _flatten_for_firestore(eval_run.model_dump(mode="json"), ["uncovered_combos"])
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
        data = _flatten_for_firestore(conversation.model_dump(mode="json"), ["combos_satisfied"])
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
            decoded = _decode_run_doc(raw_data)
            try:
                run = eval_run_entity.EvalRun.model_validate(decoded)
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
        decoded = _decode_run_doc(raw_data)
        return eval_run_entity.EvalRun.model_validate(decoded)

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
            decoded = _decode_conversation_doc(raw_data)
            try:
                conv = eval_run_entity.EvalRunConversationSnapshot.model_validate(decoded)
            except pydantic.ValidationError:
                continue
            conversations.append(conv)
        return conversations
