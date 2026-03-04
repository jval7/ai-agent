import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.ports.blacklist_repository_port as blacklist_repository_port


class FirestoreBlacklistRepositoryAdapter(blacklist_repository_port.BlacklistRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, entry: blacklist_entry_entity.BlacklistEntry) -> None:
        entry_document = firestore_paths.tenant_blacklist_entry_document(
            self._client,
            entry.tenant_id,
            entry.whatsapp_user_id,
        )
        entry_data = firestore_model_mapper.model_to_document(entry)
        try:
            entry_document.set(entry_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save blacklist entry in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save blacklist entry in firestore"
            ) from error

    def delete(self, tenant_id: str, whatsapp_user_id: str) -> None:
        entry_document = firestore_paths.tenant_blacklist_entry_document(
            self._client,
            tenant_id,
            whatsapp_user_id,
        )
        try:
            entry_document.delete()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete blacklist entry from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete blacklist entry from firestore"
            ) from error

    def exists(self, tenant_id: str, whatsapp_user_id: str) -> bool:
        entry_document = firestore_paths.tenant_blacklist_entry_document(
            self._client,
            tenant_id,
            whatsapp_user_id,
        )
        try:
            snapshot = entry_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read blacklist entry from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read blacklist entry from firestore"
            ) from error
        return bool(snapshot.exists)

    def list_by_tenant(self, tenant_id: str) -> list[blacklist_entry_entity.BlacklistEntry]:
        entries_collection = firestore_paths.tenant_blacklist_entries_collection(
            self._client, tenant_id
        )
        try:
            snapshots = list(entries_collection.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list blacklist entries from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list blacklist entries from firestore"
            ) from error

        entries: list[blacklist_entry_entity.BlacklistEntry] = []
        for snapshot in snapshots:
            entry_raw_data = snapshot.to_dict()
            if entry_raw_data is None:
                continue
            entry = firestore_model_mapper.parse_document(
                entry_raw_data,
                blacklist_entry_entity.BlacklistEntry,
                "blacklist entry",
            )
            if entry.tenant_id == tenant_id:
                entries.append(entry)
        return entries
