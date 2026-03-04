import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port


class FirestoreWhatsappConnectionRepositoryAdapter(
    whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, connection: whatsapp_connection_entity.WhatsappConnection) -> None:
        connection_document = firestore_paths.tenant_whatsapp_connection_document(
            self._client,
            connection.tenant_id,
        )
        existing_connection = self.get_by_tenant_id(connection.tenant_id)
        connection_data = firestore_model_mapper.model_to_document(connection)

        batch = self._client.batch()
        batch.set(connection_document, connection_data)

        if existing_connection is not None:
            if (
                existing_connection.embedded_signup_state is not None
                and existing_connection.embedded_signup_state != connection.embedded_signup_state
            ):
                old_signup_state_index_document = (
                    firestore_paths.whatsapp_signup_state_index_document(
                        self._client,
                        existing_connection.embedded_signup_state,
                    )
                )
                batch.delete(old_signup_state_index_document)
            if (
                existing_connection.phone_number_id is not None
                and existing_connection.phone_number_id != connection.phone_number_id
            ):
                old_phone_index_document = firestore_paths.whatsapp_phone_index_document(
                    self._client,
                    existing_connection.phone_number_id,
                )
                batch.delete(old_phone_index_document)

        if connection.embedded_signup_state is not None:
            signup_state_index_document = firestore_paths.whatsapp_signup_state_index_document(
                self._client,
                connection.embedded_signup_state,
            )
            batch.set(
                signup_state_index_document,
                {"tenant_id": connection.tenant_id},
            )
        if connection.phone_number_id is not None:
            phone_index_document = firestore_paths.whatsapp_phone_index_document(
                self._client,
                connection.phone_number_id,
            )
            batch.set(phone_index_document, {"tenant_id": connection.tenant_id})

        try:
            batch.commit()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save whatsapp connection in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save whatsapp connection in firestore"
            ) from error

    def get_by_tenant_id(
        self,
        tenant_id: str,
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        connection_document = firestore_paths.tenant_whatsapp_connection_document(
            self._client, tenant_id
        )
        try:
            snapshot = connection_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp connection from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp connection from firestore"
            ) from error
        if not snapshot.exists:
            return None
        connection_raw_data = snapshot.to_dict()
        if connection_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            connection_raw_data,
            whatsapp_connection_entity.WhatsappConnection,
            "whatsapp connection",
        )

    def get_by_phone_number_id(
        self,
        phone_number_id: str,
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        phone_index_document = firestore_paths.whatsapp_phone_index_document(
            self._client,
            phone_number_id,
        )
        try:
            index_snapshot = phone_index_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp connection from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp connection from firestore"
            ) from error
        if not index_snapshot.exists:
            return None

        index_raw_data = index_snapshot.to_dict()
        if index_raw_data is None:
            return None
        tenant_id_value = index_raw_data.get("tenant_id")
        if not isinstance(tenant_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid whatsapp phone index format in firestore"
            )
        return self.get_by_tenant_id(tenant_id_value)

    def get_by_embedded_signup_state(
        self,
        embedded_signup_state: str,
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        signup_state_index_document = firestore_paths.whatsapp_signup_state_index_document(
            self._client,
            embedded_signup_state,
        )
        try:
            index_snapshot = signup_state_index_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp connection from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp connection from firestore"
            ) from error
        if not index_snapshot.exists:
            return None

        index_raw_data = index_snapshot.to_dict()
        if index_raw_data is None:
            return None
        tenant_id_value = index_raw_data.get("tenant_id")
        if not isinstance(tenant_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid whatsapp signup state index format in firestore"
            )
        return self.get_by_tenant_id(tenant_id_value)
