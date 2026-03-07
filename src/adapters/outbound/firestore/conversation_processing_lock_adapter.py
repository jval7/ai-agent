import datetime

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.paths as firestore_paths
import src.ports.conversation_processing_lock_port as conversation_processing_lock_port


class FirestoreConversationProcessingLockAdapter(
    conversation_processing_lock_port.ConversationProcessingLockPort
):
    _lock_timeout_seconds = 120

    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def try_acquire(
        self,
        tenant_id: str,
        conversation_id: str,
        holder_id: str,
        acquired_at: datetime.datetime,
    ) -> bool:
        lock_document = firestore_paths.tenant_conversation_processing_lock_document(
            self._client,
            tenant_id,
            conversation_id,
        )
        lock_data: dict[str, object] = {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "holder_id": holder_id,
            "status": "LOCKED",
            "acquired_at": acquired_at,
        }
        lock_expiration_time = acquired_at - datetime.timedelta(seconds=self._lock_timeout_seconds)
        transaction = self._client.transaction()

        @google_cloud_firestore.transactional  # type: ignore
        def _acquire(
            current_transaction: google_cloud_firestore.Transaction,
        ) -> bool:
            snapshot = lock_document.get(transaction=current_transaction)
            if not snapshot.exists:
                current_transaction.create(lock_document, lock_data)
                return True

            current_data = snapshot.to_dict()
            if current_data is None:
                return False

            current_status = current_data.get("status")
            if current_status == "RELEASED":
                current_transaction.set(lock_document, lock_data, merge=True)
                return True

            if current_status == "LOCKED":
                acquired_at_value = current_data.get("acquired_at")
                if (
                    isinstance(acquired_at_value, datetime.datetime)
                    and acquired_at_value <= lock_expiration_time
                ):
                    current_transaction.set(lock_document, lock_data, merge=True)
                    return True

            return False

        try:
            return bool(_acquire(transaction))
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to acquire conversation processing lock in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to acquire conversation processing lock in firestore"
            ) from error

    def release(
        self,
        tenant_id: str,
        conversation_id: str,
        holder_id: str,
    ) -> None:
        lock_document = firestore_paths.tenant_conversation_processing_lock_document(
            self._client,
            tenant_id,
            conversation_id,
        )
        release_data: dict[str, object] = {
            "status": "RELEASED",
            "holder_id": holder_id,
        }
        try:
            lock_document.set(release_data, merge=True)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to release conversation processing lock in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to release conversation processing lock in firestore"
            ) from error
