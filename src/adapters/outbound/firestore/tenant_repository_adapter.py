import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.tenant as tenant_entity
import src.ports.tenant_repository_port as tenant_repository_port


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
