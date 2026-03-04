import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.user as user_entity
import src.ports.user_repository_port as user_repository_port


class FirestoreUserRepositoryAdapter(user_repository_port.UserRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, user: user_entity.User) -> None:
        user_document = firestore_paths.tenant_user_document(self._client, user.tenant_id, user.id)
        email_index_document = firestore_paths.user_email_index_document(
            self._client,
            user.email.lower(),
        )
        user_id_index_document = firestore_paths.user_id_index_document(self._client, user.id)
        user_data = firestore_model_mapper.model_to_document(user)

        old_email: str | None = None
        try:
            existing_snapshot = user_document.get()
            if existing_snapshot.exists:
                existing_user_raw_data = existing_snapshot.to_dict()
                if existing_user_raw_data is not None:
                    existing_user = firestore_model_mapper.parse_document(
                        existing_user_raw_data,
                        user_entity.User,
                        "user",
                    )
                    old_email = existing_user.email.lower()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save user in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save user in firestore"
            ) from error

        email_index_data: dict[str, str] = {
            "tenant_id": user.tenant_id,
            "user_id": user.id,
        }
        user_id_index_data: dict[str, str] = {
            "tenant_id": user.tenant_id,
            "email": user.email.lower(),
        }
        batch = self._client.batch()
        batch.set(user_document, user_data)
        batch.set(email_index_document, email_index_data)
        batch.set(user_id_index_document, user_id_index_data)
        if old_email is not None and old_email != user.email.lower():
            old_email_index_document = firestore_paths.user_email_index_document(
                self._client,
                old_email,
            )
            batch.delete(old_email_index_document)

        try:
            batch.commit()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save user in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save user in firestore"
            ) from error

    def get_by_email(self, email: str) -> user_entity.User | None:
        normalized_email = email.lower()
        email_index_document = firestore_paths.user_email_index_document(
            self._client,
            normalized_email,
        )

        try:
            email_index_snapshot = email_index_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by email from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by email from firestore"
            ) from error

        if not email_index_snapshot.exists:
            return None
        email_index_raw_data = email_index_snapshot.to_dict()
        if email_index_raw_data is None:
            return None

        tenant_id_value = email_index_raw_data.get("tenant_id")
        user_id_value = email_index_raw_data.get("user_id")
        if not isinstance(tenant_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid user email index format in firestore"
            )
        if not isinstance(user_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid user email index format in firestore"
            )

        user_document = firestore_paths.tenant_user_document(
            self._client, tenant_id_value, user_id_value
        )
        try:
            user_snapshot = user_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by email from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by email from firestore"
            ) from error
        if not user_snapshot.exists:
            return None
        user_raw_data = user_snapshot.to_dict()
        if user_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(user_raw_data, user_entity.User, "user")

    def get_by_id(self, user_id: str) -> user_entity.User | None:
        user_id_index_document = firestore_paths.user_id_index_document(self._client, user_id)
        try:
            user_id_index_snapshot = user_id_index_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by id from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by id from firestore"
            ) from error
        if not user_id_index_snapshot.exists:
            return None

        user_id_index_raw_data = user_id_index_snapshot.to_dict()
        if user_id_index_raw_data is None:
            return None
        tenant_id_value = user_id_index_raw_data.get("tenant_id")
        if not isinstance(tenant_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid user id index format in firestore"
            )

        user_document = firestore_paths.tenant_user_document(self._client, tenant_id_value, user_id)
        try:
            user_snapshot = user_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by id from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read user by id from firestore"
            ) from error
        if not user_snapshot.exists:
            return None
        user_raw_data = user_snapshot.to_dict()
        if user_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(user_raw_data, user_entity.User, "user")
