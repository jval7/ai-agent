import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.services.dto.agent_dto as agent_dto
import src.services.use_cases.agent_service as agent_service
import tests.fakes.fake_adapters as fake_adapters


def build_agent_settings_service() -> agent_service.AgentService:
    store = in_memory_store.InMemoryStore()
    repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    return agent_service.AgentService(
        agent_profile_repository=repository,
        clock=clock,
        default_system_prompt="default-prompt",
    )


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


def test_update_agent_settings_saves_office_location_and_virtual_instructions() -> None:
    service = build_agent_settings_service()

    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=5,
            office_location=agent_dto.OfficeLocationDTO(
                address="Calle 5 # 38-25, Cali",
                arrival_instructions="Llegar 20 minutos antes",
            ),
            virtual_session_instructions="Link de Meet se envía al correo 24h antes.",
        ),
    )

    assert result.office_location is not None
    assert result.office_location.address == "Calle 5 # 38-25, Cali"
    assert result.office_location.arrival_instructions == "Llegar 20 minutos antes"
    assert result.virtual_session_instructions == "Link de Meet se envía al correo 24h antes."


def test_get_agent_settings_returns_office_location_after_save() -> None:
    service = build_agent_settings_service()

    service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            office_location=agent_dto.OfficeLocationDTO(address="Carrera 1 # 2-3, Bogota"),
        ),
    )

    fetched = service.get_agent_settings("tenant-1")

    assert fetched.office_location is not None
    assert fetched.office_location.address == "Carrera 1 # 2-3, Bogota"
    assert fetched.office_location.arrival_instructions is None


def test_update_agent_settings_office_location_none_clears_field() -> None:
    service = build_agent_settings_service()

    service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            office_location=agent_dto.OfficeLocationDTO(address="Carrera 1 # 2-3"),
        ),
    )
    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            office_location=None,
        ),
    )

    assert result.office_location is None


def test_virtual_session_instructions_whitespace_normalized_to_none() -> None:
    service = build_agent_settings_service()

    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            virtual_session_instructions="   ",
        ),
    )

    assert result.virtual_session_instructions is None
