import datetime

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.processed_webhook_event as processed_webhook_event_entity
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port


class FirestoreProcessedWebhookEventRepositoryAdapter(
    processed_webhook_event_repository_port.ProcessedWebhookEventRepositoryPort
):
    _claim_timeout_seconds = 120

    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def claim_for_processing(
        self,
        tenant_id: str,
        provider_event_id: str,
        claimed_at: datetime.datetime,
    ) -> bool:
        event_document = firestore_paths.tenant_processed_webhook_event_document(
            self._client,
            tenant_id,
            provider_event_id,
        )
        event_data: dict[str, object] = {
            "tenant_id": tenant_id,
            "provider_event_id": provider_event_id,
            "status": "CLAIMED",
            "claimed_at": claimed_at,
            "processed_at": None,
            "failed_at": None,
            "failure_reason": None,
        }
        claim_expiration_time = claimed_at - datetime.timedelta(seconds=self._claim_timeout_seconds)
        transaction = self._client.transaction()

        @google_cloud_firestore.transactional  # type: ignore[misc]
        def _claim(
            current_transaction: google_cloud_firestore.Transaction,
        ) -> bool:
            snapshot = event_document.get(transaction=current_transaction)
            if not snapshot.exists:
                current_transaction.create(event_document, event_data)
                return True

            current_data = snapshot.to_dict()
            if current_data is None:
                return False

            current_status = current_data.get("status")
            if current_status == "FAILED":
                current_transaction.set(event_document, event_data, merge=True)
                return True

            if current_status == "CLAIMED":
                claimed_at_value = current_data.get("claimed_at")
                if (
                    isinstance(claimed_at_value, datetime.datetime)
                    and claimed_at_value <= claim_expiration_time
                ):
                    current_transaction.set(event_document, event_data, merge=True)
                    return True

            return False

        try:
            return bool(_claim(transaction))
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to claim processed webhook event in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to claim processed webhook event in firestore"
            ) from error

    def mark_processed(
        self,
        tenant_id: str,
        provider_event_id: str,
        processed_at: datetime.datetime,
    ) -> None:
        event_document = firestore_paths.tenant_processed_webhook_event_document(
            self._client,
            tenant_id,
            provider_event_id,
        )
        event_data: dict[str, object] = {
            "tenant_id": tenant_id,
            "provider_event_id": provider_event_id,
            "status": "PROCESSED",
            "processed_at": processed_at,
            "failed_at": None,
            "failure_reason": None,
        }
        try:
            event_document.set(event_data, merge=True)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to mark processed webhook event in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to mark processed webhook event in firestore"
            ) from error

    def mark_failed(
        self,
        tenant_id: str,
        provider_event_id: str,
        failed_at: datetime.datetime,
        failure_reason: str,
    ) -> None:
        event_document = firestore_paths.tenant_processed_webhook_event_document(
            self._client,
            tenant_id,
            provider_event_id,
        )
        event_data: dict[str, object] = {
            "tenant_id": tenant_id,
            "provider_event_id": provider_event_id,
            "status": "FAILED",
            "failed_at": failed_at,
            "failure_reason": failure_reason,
        }
        try:
            event_document.set(event_data, merge=True)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to mark failed webhook event in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to mark failed webhook event in firestore"
            ) from error

    def exists(self, tenant_id: str, provider_event_id: str) -> bool:
        event_document = firestore_paths.tenant_processed_webhook_event_document(
            self._client,
            tenant_id,
            provider_event_id,
        )
        try:
            snapshot = event_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read processed webhook event from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read processed webhook event from firestore"
            ) from error
        return bool(snapshot.exists)

    def save(self, event: processed_webhook_event_entity.ProcessedWebhookEvent) -> None:
        event_document = firestore_paths.tenant_processed_webhook_event_document(
            self._client,
            event.tenant_id,
            event.provider_event_id,
        )
        event_data = firestore_model_mapper.model_to_document(event)
        try:
            event_document.set(event_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save processed webhook event in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save processed webhook event in firestore"
            ) from error
