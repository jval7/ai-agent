import abc

import src.domain.entities.agent_profile as agent_profile_entity


class AgentProfileRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, agent_profile: agent_profile_entity.AgentProfile) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_tenant_id(self, tenant_id: str) -> agent_profile_entity.AgentProfile | None:
        raise NotImplementedError
