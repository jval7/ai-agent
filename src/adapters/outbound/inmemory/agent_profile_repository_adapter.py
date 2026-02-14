import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.agent_profile as agent_profile_entity
import src.ports.agent_profile_repository_port as agent_profile_repository_port


class InMemoryAgentProfileRepositoryAdapter(
    agent_profile_repository_port.AgentProfileRepositoryPort
):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, agent_profile: agent_profile_entity.AgentProfile) -> None:
        with self._store.lock:
            self._store.agent_profile_by_tenant[agent_profile.tenant_id] = agent_profile.model_copy(
                deep=True
            )
            self._store.flush()

    def get_by_tenant_id(self, tenant_id: str) -> agent_profile_entity.AgentProfile | None:
        with self._store.lock:
            agent_profile = self._store.agent_profile_by_tenant.get(tenant_id)
            if agent_profile is None:
                return None
            return agent_profile.model_copy(deep=True)
