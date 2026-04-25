import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.booking_constants as booking_constants
import src.domain.entities.agent_profile as agent_profile_entity
import src.services.use_cases.event_description_builder as event_description_builder_mod


def _build_builder(
    office_location: agent_profile_entity.OfficeLocation | None = None,
) -> event_description_builder_mod.EventDescriptionBuilder:
    store = in_memory_store.InMemoryStore()
    repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    if office_location is not None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            system_prompt="prompt",
            office_location=office_location,
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        repository.save(profile)
    return event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=repository,
    )


class TestEventDescriptionBuilderPresencial:
    def test_presencial_with_full_office_location(self) -> None:
        builder = _build_builder(
            office_location=agent_profile_entity.OfficeLocation(
                address="Calle 5 # 38-25, Cali",
                arrival_instructions="Llegar 20 min antes con cédula",
            )
        )
        result = builder.build(
            tenant_id="t-1",
            modality="PRESENCIAL",
        )
        assert "Motivo de consulta" not in result.description
        assert "Calle 5 # 38-25, Cali" in result.description
        assert "Llegar 20 min antes con cédula" in result.description
        assert result.location == "Calle 5 # 38-25, Cali"

    def test_presencial_without_optional_office_fields(self) -> None:
        builder = _build_builder(
            office_location=agent_profile_entity.OfficeLocation(
                address="Carrera 1 # 2-3, Bogota",
            )
        )
        result = builder.build(
            tenant_id="t-1",
            modality="PRESENCIAL",
        )
        assert "Carrera 1 # 2-3, Bogota" in result.description
        assert "Indicaciones" not in result.description
        assert result.location == "Carrera 1 # 2-3, Bogota"

    def test_presencial_without_office_location_yields_empty_description(self) -> None:
        builder = _build_builder()
        result = builder.build(
            tenant_id="t-1",
            modality="PRESENCIAL",
        )
        assert result.description == ""
        assert result.location is None

    def test_presencial_with_no_agent_profile_at_all(self) -> None:
        store = in_memory_store.InMemoryStore()
        repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
        builder = event_description_builder_mod.EventDescriptionBuilder(
            agent_profile_repository=repository,
        )
        result = builder.build(
            tenant_id="t-unknown",
            modality="PRESENCIAL",
        )
        assert result.location is None


class TestEventDescriptionBuilderVirtual:
    def test_virtual_always_uses_domain_constant(self) -> None:
        """VIRTUAL descriptions always include the product-wide constant."""
        builder = _build_builder()
        result = builder.build(
            tenant_id="t-1",
            modality="VIRTUAL",
        )
        assert "Motivo de consulta" not in result.description
        assert booking_constants.VIRTUAL_SESSION_INSTRUCTIONS in result.description
        assert result.location is None

    def test_virtual_constant_present_even_without_agent_profile(self) -> None:
        store = in_memory_store.InMemoryStore()
        repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
        builder = event_description_builder_mod.EventDescriptionBuilder(
            agent_profile_repository=repository,
        )
        result = builder.build(
            tenant_id="t-unknown",
            modality="VIRTUAL",
        )
        assert booking_constants.VIRTUAL_SESSION_INSTRUCTIONS in result.description
        assert result.location is None


class TestEventDescriptionBuilderGeneral:
    def test_no_consultation_reason_does_not_appear_in_description(self) -> None:
        builder = _build_builder(
            office_location=agent_profile_entity.OfficeLocation(address="Calle 1"),
        )
        result = builder.build(
            tenant_id="t-1",
            modality="PRESENCIAL",
        )
        assert "Calle 1" in result.description
        assert "Motivo" not in result.description

    def test_unknown_modality_yields_empty_description(self) -> None:
        builder = _build_builder()
        result = builder.build(
            tenant_id="t-1",
            modality=None,
        )
        assert result.description == ""
        assert result.location is None
