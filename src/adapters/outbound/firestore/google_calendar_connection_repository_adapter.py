import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.ports.google_calendar_connection_repository_port as google_calendar_connection_repository_port


class FirestoreGoogleCalendarConnectionRepositoryAdapter(
    google_calendar_connection_repository_port.GoogleCalendarConnectionRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, connection: google_calendar_connection_entity.GoogleCalendarConnection) -> None:
        connection_document = firestore_paths.tenant_google_calendar_connection_document(
            self._client,
            connection.tenant_id,
        )
        existing_connection = self.get_by_tenant_id(connection.tenant_id)
        connection_data = firestore_model_mapper.model_to_document(connection)

        batch = self._client.batch()
        batch.set(connection_document, connection_data)
        if (
            existing_connection is not None
            and existing_connection.oauth_state is not None
            and existing_connection.oauth_state != connection.oauth_state
        ):
            old_oauth_state_index_document = firestore_paths.google_oauth_state_index_document(
                self._client,
                existing_connection.oauth_state,
            )
            batch.delete(old_oauth_state_index_document)
        if connection.oauth_state is not None:
            oauth_state_index_document = firestore_paths.google_oauth_state_index_document(
                self._client,
                connection.oauth_state,
            )
            batch.set(oauth_state_index_document, {"tenant_id": connection.tenant_id})

        try:
            batch.commit()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save google calendar connection in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save google calendar connection in firestore"
            ) from error

    def get_by_tenant_id(
        self,
        tenant_id: str,
    ) -> google_calendar_connection_entity.GoogleCalendarConnection | None:
        connection_document = firestore_paths.tenant_google_calendar_connection_document(
            self._client,
            tenant_id,
        )
        try:
            snapshot = connection_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read google calendar connection from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read google calendar connection from firestore"
            ) from error
        if not snapshot.exists:
            return None
        connection_raw_data = snapshot.to_dict()
        if connection_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            connection_raw_data,
            google_calendar_connection_entity.GoogleCalendarConnection,
            "google calendar connection",
        )

    def get_by_oauth_state(
        self,
        oauth_state: str,
    ) -> google_calendar_connection_entity.GoogleCalendarConnection | None:
        oauth_state_index_document = firestore_paths.google_oauth_state_index_document(
            self._client,
            oauth_state,
        )
        try:
            index_snapshot = oauth_state_index_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read google calendar connection from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read google calendar connection from firestore"
            ) from error
        if not index_snapshot.exists:
            return None

        index_raw_data = index_snapshot.to_dict()
        if index_raw_data is None:
            return None
        tenant_id_value = index_raw_data.get("tenant_id")
        if not isinstance(tenant_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid google oauth state index format in firestore"
            )
        return self.get_by_tenant_id(tenant_id_value)
