import datetime
import typing

import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.invitation_token as invitation_token_entity
import src.ports.invitation_token_repository_port as invitation_token_repository_port


class FirestoreInvitationTokenRepositoryAdapter(
    invitation_token_repository_port.InvitationTokenRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, token: invitation_token_entity.InvitationToken) -> None:
        token_document = firestore_paths.invitation_token_document(self._client, token.token_hash)
        token_data = firestore_model_mapper.model_to_document(token)
        try:
            token_document.set(token_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save invitation token in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save invitation token in firestore"
            ) from error

    def get_by_hash(self, token_hash: str) -> invitation_token_entity.InvitationToken | None:
        token_document = firestore_paths.invitation_token_document(self._client, token_hash)
        try:
            snapshot = token_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read invitation token from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read invitation token from firestore"
            ) from error
        if not snapshot.exists:
            return None
        record_raw_data = snapshot.to_dict()
        if record_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            record_raw_data,
            invitation_token_entity.InvitationToken,
            "invitation token",
        )

    def consume(
        self,
        token_hash: str,
        consumed_at: datetime.datetime,
    ) -> invitation_token_entity.InvitationToken | None:
        token_document = firestore_paths.invitation_token_document(self._client, token_hash)
        transaction = self._client.transaction()

        @google_cloud_firestore.transactional  # type: ignore
        def _consume(
            current_transaction: google_cloud_firestore.Transaction,
        ) -> invitation_token_entity.InvitationToken | None:
            snapshot = token_document.get(transaction=current_transaction)
            if not snapshot.exists:
                return None
            record_raw_data = snapshot.to_dict()
            if record_raw_data is None:
                return None

            token = firestore_model_mapper.parse_document(
                record_raw_data,
                invitation_token_entity.InvitationToken,
                "invitation token",
            )
            if token.consumed_at is not None:
                return None
            if token.expires_at <= consumed_at:
                return None

            current_transaction.update(token_document, {"consumed_at": consumed_at})
            updated_token = token.model_copy(deep=True)
            updated_token.consumed_at = consumed_at
            return updated_token

        try:
            result = _consume(transaction)
            return typing.cast(invitation_token_entity.InvitationToken | None, result)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to consume invitation token in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to consume invitation token in firestore"
            ) from error

    def invalidate_active_for_user(
        self,
        user_id: str,
        purpose: invitation_token_entity.InvitationPurpose,
        now: datetime.datetime,
    ) -> None:
        collection = firestore_paths.invitation_tokens_collection(self._client)
        try:
            snapshots = (
                collection.where(
                    filter=google_cloud_firestore.FieldFilter("user_id", "==", user_id)
                )
                .where(filter=google_cloud_firestore.FieldFilter("purpose", "==", purpose.value))
                .where(filter=google_cloud_firestore.FieldFilter("consumed_at", "==", None))
                .stream()
            )
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to query invitation tokens in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to query invitation tokens in firestore"
            ) from error

        for snapshot in snapshots:
            try:
                snapshot.reference.update({"consumed_at": now})
            except google_api_exceptions.NotFound:
                pass
            except google_api_exceptions.GoogleAPICallError as error:
                raise firestore_errors.FirestoreRepositoryError(
                    "failed to invalidate invitation token in firestore"
                ) from error
            except google_api_exceptions.RetryError as error:
                raise firestore_errors.FirestoreRepositoryError(
                    "failed to invalidate invitation token in firestore"
                ) from error
