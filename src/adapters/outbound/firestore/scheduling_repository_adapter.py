import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.ports.scheduling_repository_port as scheduling_repository_port


class FirestoreSchedulingRepositoryAdapter(scheduling_repository_port.SchedulingRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save_request(self, request: scheduling_request_entity.SchedulingRequest) -> None:
        request_document = firestore_paths.tenant_scheduling_request_document(
            self._client,
            request.tenant_id,
            request.id,
        )
        request_data = firestore_model_mapper.model_to_document(request)
        try:
            request_document.set(request_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save scheduling request in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save scheduling request in firestore"
            ) from error

    def get_request_by_id(
        self,
        tenant_id: str,
        request_id: str,
    ) -> scheduling_request_entity.SchedulingRequest | None:
        request_document = firestore_paths.tenant_scheduling_request_document(
            self._client,
            tenant_id,
            request_id,
        )
        try:
            snapshot = request_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read scheduling request from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read scheduling request from firestore"
            ) from error
        if not snapshot.exists:
            return None
        request_raw_data = snapshot.to_dict()
        if request_raw_data is None:
            return None
        request = firestore_model_mapper.parse_document(
            request_raw_data,
            scheduling_request_entity.SchedulingRequest,
            "scheduling request",
        )
        if request.tenant_id != tenant_id:
            return None
        return request

    def delete_request(self, tenant_id: str, request_id: str) -> None:
        request_document = firestore_paths.tenant_scheduling_request_document(
            self._client,
            tenant_id,
            request_id,
        )
        try:
            request_document.delete()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete scheduling request from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete scheduling request from firestore"
            ) from error

    def list_requests_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> list[scheduling_request_entity.SchedulingRequest]:
        requests_collection = firestore_paths.tenant_scheduling_requests_collection(
            self._client,
            tenant_id,
        )
        if status is None:
            query = requests_collection
        else:
            query = requests_collection.where("status", "==", status)

        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduling requests from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduling requests from firestore"
            ) from error

        requests: list[scheduling_request_entity.SchedulingRequest] = []
        for snapshot in snapshots:
            request_raw_data = snapshot.to_dict()
            if request_raw_data is None:
                continue
            request = firestore_model_mapper.parse_document(
                request_raw_data,
                scheduling_request_entity.SchedulingRequest,
                "scheduling request",
            )
            if request.tenant_id == tenant_id:
                requests.append(request)
        return requests

    def list_requests_by_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> list[scheduling_request_entity.SchedulingRequest]:
        requests_collection = firestore_paths.tenant_scheduling_requests_collection(
            self._client,
            tenant_id,
        )
        query = requests_collection.where("conversation_id", "==", conversation_id)
        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduling requests from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduling requests from firestore"
            ) from error

        requests: list[scheduling_request_entity.SchedulingRequest] = []
        for snapshot in snapshots:
            request_raw_data = snapshot.to_dict()
            if request_raw_data is None:
                continue
            request = firestore_model_mapper.parse_document(
                request_raw_data,
                scheduling_request_entity.SchedulingRequest,
                "scheduling request",
            )
            if request.tenant_id == tenant_id:
                requests.append(request)
        return requests
