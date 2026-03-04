import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.agent_profile as agent_profile_entity
import src.ports.agent_profile_repository_port as agent_profile_repository_port


class FirestoreAgentProfileRepositoryAdapter(
    agent_profile_repository_port.AgentProfileRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, agent_profile: agent_profile_entity.AgentProfile) -> None:
        profile_document = firestore_paths.tenant_agent_profile_document(
            self._client,
            agent_profile.tenant_id,
        )
        profile_data = firestore_model_mapper.model_to_document(agent_profile)
        try:
            profile_document.set(profile_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save agent profile in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save agent profile in firestore"
            ) from error

    def get_by_tenant_id(self, tenant_id: str) -> agent_profile_entity.AgentProfile | None:
        profile_document = firestore_paths.tenant_agent_profile_document(self._client, tenant_id)
        try:
            snapshot = profile_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read agent profile from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read agent profile from firestore"
            ) from error
        if not snapshot.exists:
            return None
        profile_raw_data = snapshot.to_dict()
        if profile_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            profile_raw_data,
            agent_profile_entity.AgentProfile,
            "agent profile",
        )
