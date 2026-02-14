import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.services.dto.agent_dto as agent_dto
import src.services.use_cases.agent_service as agent_service
import tests.fakes.fake_adapters as fake_adapters


def build_agent_service() -> agent_service.AgentService:
    store = in_memory_store.InMemoryStore()
    repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    return agent_service.AgentService(
        agent_profile_repository=repository,
        clock=clock,
        default_system_prompt="default-prompt",
    )


def test_get_system_prompt_creates_default_if_missing() -> None:
    service = build_agent_service()

    result = service.get_system_prompt("tenant-1")

    assert result.tenant_id == "tenant-1"
    assert result.system_prompt == "default-prompt"


def test_update_system_prompt_replaces_value() -> None:
    service = build_agent_service()

    updated = service.update_system_prompt(
        "tenant-1",
        agent_dto.UpdateSystemPromptDTO(system_prompt="custom prompt"),
    )

    fetched = service.get_system_prompt("tenant-1")

    assert updated.system_prompt == "custom prompt"
    assert fetched.system_prompt == "custom prompt"
