import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.paths as firestore_paths
import src.ports.memory_admin_port as memory_admin_port


class FirestoreMemoryAdminAdapter(memory_admin_port.MemoryAdminPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def reset_state(self) -> None:
        try:
            self._client.recursive_delete(
                firestore_paths.tenants_collection(self._client),
                chunk_size=200,
            )
            self._client.recursive_delete(
                self._client.collection(firestore_paths.INDEXES_COLLECTION),
                chunk_size=200,
            )
            self._client.recursive_delete(
                self._client.collection(firestore_paths.REFRESH_TOKENS_COLLECTION),
                chunk_size=200,
            )
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to reset firestore state"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to reset firestore state"
            ) from error

    def reset_chat_state(self) -> None:
        try:
            tenant_documents = list(
                firestore_paths.tenants_collection(self._client).list_documents()
            )
            for tenant_document in tenant_documents:
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.WHATSAPP_USERS_COLLECTION),
                    chunk_size=200,
                )
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.PATIENTS_COLLECTION),
                    chunk_size=200,
                )
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.CONVERSATION_LOOKUP_COLLECTION),
                    chunk_size=200,
                )
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.CONVERSATIONS_COLLECTION),
                    chunk_size=200,
                )
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.SCHEDULING_REQUESTS_COLLECTION),
                    chunk_size=200,
                )
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.PROCESSED_WEBHOOK_EVENTS_COLLECTION),
                    chunk_size=200,
                )
                self._client.recursive_delete(
                    tenant_document.collection(firestore_paths.BLACKLIST_ENTRIES_COLLECTION),
                    chunk_size=200,
                )
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to reset firestore chat state"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to reset firestore chat state"
            ) from error
