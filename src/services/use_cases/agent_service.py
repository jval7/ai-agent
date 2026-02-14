import src.domain.entities.agent_profile as agent_profile_entity
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.services.dto.agent_dto as agent_dto


class AgentService:
    def __init__(
        self,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        clock: clock_port.ClockPort,
        default_system_prompt: str,
    ) -> None:
        self._agent_profile_repository = agent_profile_repository
        self._clock = clock
        self._default_system_prompt = default_system_prompt

    def get_system_prompt(self, tenant_id: str) -> agent_dto.SystemPromptResponseDTO:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            now_value = self._clock.now()
            agent_profile = agent_profile_entity.AgentProfile(
                tenant_id=tenant_id,
                system_prompt=self._default_system_prompt,
                updated_at=now_value,
            )
            self._agent_profile_repository.save(agent_profile)

        return agent_dto.SystemPromptResponseDTO(
            tenant_id=tenant_id,
            system_prompt=agent_profile.system_prompt,
        )

    def update_system_prompt(
        self, tenant_id: str, update_dto: agent_dto.UpdateSystemPromptDTO
    ) -> agent_dto.SystemPromptResponseDTO:
        now_value = self._clock.now()
        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt=update_dto.system_prompt,
            updated_at=now_value,
        )
        self._agent_profile_repository.save(agent_profile)
        return agent_dto.SystemPromptResponseDTO(
            tenant_id=tenant_id,
            system_prompt=agent_profile.system_prompt,
        )
