import datetime

import src.domain.entities.agent_profile as agent_profile_entity
import src.services.agentic.prompts.office_context_section as office_context_section
import src.services.agentic.state_models as agentic_state_models


def _build_context() -> agentic_state_models.RuntimePromptContext:
    return agentic_state_models.RuntimePromptContext(
        state="POST_BOOKING_FOLLOWUP",
        enabled_tool_names=["close_session"],
    )


def _build_profile_with_office(
    address: str = "Calle 5 # 38-25, Cali",
    arrival_instructions: str | None = "Llegar 20 min antes",
    access_notes: str | None = "Edificio azul, piso 3",
    virtual_session_instructions: str | None = None,
) -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="t-1",
        system_prompt="prompt",
        office_location=agent_profile_entity.OfficeLocation(
            address=address,
            arrival_instructions=arrival_instructions,
            access_notes=access_notes,
        ),
        virtual_session_instructions=virtual_session_instructions,
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


def _build_profile_virtual_only(
    instructions: str = "Link de Meet llega al correo 24h antes.",
) -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="t-1",
        system_prompt="prompt",
        virtual_session_instructions=instructions,
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


class TestOfficeContextSection:
    def test_renders_nothing_when_agent_profile_is_none(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        result = section.render(ctx, known_patient=None, agent_profile=None)
        assert result == []

    def test_renders_nothing_when_no_office_or_virtual(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            system_prompt="prompt",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        assert result == []

    def test_renders_office_location_with_all_fields(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_with_office()
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Datos del consultorio" in joined
        assert "Calle 5 # 38-25, Cali" in joined
        assert "Llegar 20 min antes" in joined
        assert "Edificio azul, piso 3" in joined

    def test_renders_office_location_without_optional_fields(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_with_office(arrival_instructions=None, access_notes=None)
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Calle 5 # 38-25, Cali" in joined
        assert "Indicaciones" not in joined
        assert "Notas" not in joined

    def test_renders_virtual_only(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_virtual_only()
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Datos del consultorio" in joined
        assert "Link de Meet llega al correo 24h antes." in joined
        assert "Dirección" not in joined

    def test_renders_both_office_and_virtual(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_with_office(
            virtual_session_instructions="Videollamada por Google Meet."
        )
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Calle 5 # 38-25, Cali" in joined
        assert "Videollamada por Google Meet." in joined
