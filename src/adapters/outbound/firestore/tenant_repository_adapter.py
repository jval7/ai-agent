import logging

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.tenant as tenant_entity
import src.ports.tenant_repository_port as tenant_repository_port

logger = logging.getLogger(__name__)


class FirestoreTenantRepositoryAdapter(tenant_repository_port.TenantRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, tenant: tenant_entity.Tenant) -> None:
        tenant_document = firestore_paths.tenant_document(self._client, tenant.id)
        tenant_data = firestore_model_mapper.model_to_document(tenant)
        try:
            tenant_document.set(tenant_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save tenant in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save tenant in firestore"
            ) from error

    def get_by_id(self, tenant_id: str) -> tenant_entity.Tenant | None:
        tenant_document = firestore_paths.tenant_document(self._client, tenant_id)
        try:
            snapshot = tenant_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tenant from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tenant from firestore"
            ) from error

        if not snapshot.exists:
            return None

        tenant_raw_data = snapshot.to_dict()
        if tenant_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            tenant_raw_data, tenant_entity.Tenant, "tenant"
        )

    def delete_with_data(self, tenant_id: str) -> bool:
        tenant_doc_ref = firestore_paths.tenant_document(self._client, tenant_id)
        try:
            snapshot = tenant_doc_ref.get()
        except (
            google_api_exceptions.GoogleAPICallError,
            google_api_exceptions.RetryError,
        ) as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tenant from firestore"
            ) from error

        if not snapshot.exists:
            return False

        self._delete_global_indexes(tenant_id)

        try:
            self._client.recursive_delete(tenant_doc_ref)
        except (
            google_api_exceptions.GoogleAPICallError,
            google_api_exceptions.RetryError,
        ) as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete tenant from firestore"
            ) from error

        return True

    def _delete_global_indexes(self, tenant_id: str) -> None:
        users_collection = firestore_paths.tenant_users_collection(self._client, tenant_id)
        for user_snapshot in users_collection.stream():
            user_data = user_snapshot.to_dict()
            if user_data is not None:
                email = user_data.get("email")
                if isinstance(email, str):
                    firestore_paths.user_email_index_document(
                        self._client, email.lower()
                    ).delete()
            firestore_paths.user_id_index_document(
                self._client, user_snapshot.id
            ).delete()
            logger.info("deleted user indexes for user_id=%s", user_snapshot.id)

        wa_conn_ref = firestore_paths.tenant_whatsapp_connection_document(
            self._client, tenant_id
        )
        wa_snap = wa_conn_ref.get()
        if wa_snap.exists:
            wa_data = wa_snap.to_dict()
            if wa_data is not None:
                phone_id = wa_data.get("phone_number_id")
                if isinstance(phone_id, str):
                    firestore_paths.whatsapp_phone_index_document(
                        self._client, phone_id
                    ).delete()
                signup_state = wa_data.get("embedded_signup_state")
                if isinstance(signup_state, str):
                    firestore_paths.whatsapp_signup_state_index_document(
                        self._client, signup_state
                    ).delete()

        gcal_ref = firestore_paths.tenant_google_calendar_connection_document(
            self._client, tenant_id
        )
        gcal_snap = gcal_ref.get()
        if gcal_snap.exists:
            gcal_data = gcal_snap.to_dict()
            if gcal_data is not None:
                oauth_state = gcal_data.get("oauth_state")
                if isinstance(oauth_state, str):
                    firestore_paths.google_oauth_state_index_document(
                        self._client, oauth_state
                    ).delete()
