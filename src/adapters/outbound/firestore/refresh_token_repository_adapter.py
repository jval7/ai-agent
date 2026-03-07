import datetime
import typing

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.refresh_token as refresh_token_entity
import src.ports.refresh_token_repository_port as refresh_token_repository_port


class FirestoreRefreshTokenRepositoryAdapter(
    refresh_token_repository_port.RefreshTokenRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def create(self, record: refresh_token_entity.RefreshTokenRecord) -> None:
        record_document = firestore_paths.refresh_token_document(self._client, record.jti)
        record_data = firestore_model_mapper.model_to_document(record)
        try:
            record_document.create(record_data)
        except google_api_exceptions.AlreadyExists as error:
            raise firestore_errors.FirestoreRepositoryError(
                "refresh token already exists in firestore"
            ) from error
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save refresh token in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save refresh token in firestore"
            ) from error

    def get_by_jti(self, jti: str) -> refresh_token_entity.RefreshTokenRecord | None:
        record_document = firestore_paths.refresh_token_document(self._client, jti)
        try:
            snapshot = record_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read refresh token from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read refresh token from firestore"
            ) from error
        if not snapshot.exists:
            return None
        record_raw_data = snapshot.to_dict()
        if record_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            record_raw_data,
            refresh_token_entity.RefreshTokenRecord,
            "refresh token",
        )

    def consume_for_rotation(
        self,
        jti: str,
        tenant_id: str,
        user_id: str,
        token_hash: str,
        revoked_at: datetime.datetime,
    ) -> refresh_token_entity.RefreshTokenRecord | None:
        record_document = firestore_paths.refresh_token_document(self._client, jti)
        transaction = self._client.transaction()

        @google_cloud_firestore.transactional  # type: ignore
        def _consume(
            current_transaction: google_cloud_firestore.Transaction,
        ) -> refresh_token_entity.RefreshTokenRecord | None:
            snapshot = record_document.get(transaction=current_transaction)
            if not snapshot.exists:
                return None
            record_raw_data = snapshot.to_dict()
            if record_raw_data is None:
                return None

            record = firestore_model_mapper.parse_document(
                record_raw_data,
                refresh_token_entity.RefreshTokenRecord,
                "refresh token",
            )
            if record.tenant_id != tenant_id:
                return None
            if record.user_id != user_id:
                return None
            if record.token_hash != token_hash:
                return None
            if record.revoked_at is not None:
                return None
            if record.expires_at <= revoked_at:
                return None

            current_transaction.update(record_document, {"revoked_at": revoked_at})
            updated_record = record.model_copy(deep=True)
            updated_record.revoked_at = revoked_at
            return updated_record

        try:
            result = _consume(transaction)
            return typing.cast(refresh_token_entity.RefreshTokenRecord | None, result)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to consume refresh token in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to consume refresh token in firestore"
            ) from error

    def revoke(self, jti: str, revoked_at: datetime.datetime) -> bool:
        record_document = firestore_paths.refresh_token_document(self._client, jti)
        try:
            snapshot = record_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to revoke refresh token in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to revoke refresh token in firestore"
            ) from error
        if not snapshot.exists:
            return False
        try:
            record_document.update({"revoked_at": revoked_at})
        except google_api_exceptions.NotFound:
            return False
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to revoke refresh token in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to revoke refresh token in firestore"
            ) from error
        return True
