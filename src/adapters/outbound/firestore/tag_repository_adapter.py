import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.tag as tag_entity
import src.ports.tag_repository_port as tag_repository_port


class FirestoreTagRepositoryAdapter(tag_repository_port.TagRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, tag: tag_entity.Tag) -> None:
        tag_document = firestore_paths.tenant_tag_document(
            self._client,
            tag.tenant_id,
            tag.id,
        )
        tag_data = firestore_model_mapper.model_to_document(tag)
        try:
            tag_document.set(tag_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save tag in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save tag in firestore"
            ) from error

    def get_by_id(self, tenant_id: str, tag_id: str) -> tag_entity.Tag | None:
        tag_document = firestore_paths.tenant_tag_document(
            self._client,
            tenant_id,
            tag_id,
        )
        try:
            snapshot = tag_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tag from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tag from firestore"
            ) from error
        if not snapshot.exists:
            return None

        tag_raw_data = snapshot.to_dict()
        if tag_raw_data is None:
            return None
        tag = firestore_model_mapper.parse_document(
            tag_raw_data,
            tag_entity.Tag,
            "tag",
        )
        if tag.tenant_id != tenant_id:
            return None
        return tag

    def get_by_slug(self, tenant_id: str, slug: str) -> tag_entity.Tag | None:
        tags_collection = firestore_paths.tenant_tags_collection(self._client, tenant_id)
        try:
            query = tags_collection.where("slug", "==", slug).limit(1)
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tag by slug from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read tag by slug from firestore"
            ) from error

        for snapshot in snapshots:
            tag_raw_data = snapshot.to_dict()
            if tag_raw_data is None:
                continue
            tag = firestore_model_mapper.parse_document(
                tag_raw_data,
                tag_entity.Tag,
                "tag",
            )
            if tag.tenant_id == tenant_id:
                return tag
        return None

    def list_by_tenant(self, tenant_id: str) -> list[tag_entity.Tag]:
        tags_collection = firestore_paths.tenant_tags_collection(self._client, tenant_id)
        try:
            snapshots = list(tags_collection.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list tags from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list tags from firestore"
            ) from error

        tags: list[tag_entity.Tag] = []
        for snapshot in snapshots:
            tag_raw_data = snapshot.to_dict()
            if tag_raw_data is None:
                continue
            tag = firestore_model_mapper.parse_document(
                tag_raw_data,
                tag_entity.Tag,
                "tag",
            )
            if tag.tenant_id == tenant_id:
                tags.append(tag)
        return tags

    def delete(self, tenant_id: str, tag_id: str) -> None:
        tag_document = firestore_paths.tenant_tag_document(
            self._client,
            tenant_id,
            tag_id,
        )
        try:
            tag_document.delete()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete tag from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete tag from firestore"
            ) from error
