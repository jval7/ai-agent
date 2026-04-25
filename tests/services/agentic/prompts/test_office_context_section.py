import datetime

import src.domain.booking_constants as booking_constants
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
) -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="t-1",
        system_prompt="prompt",
        office_location=agent_profile_entity.OfficeLocation(
            address=address,
            arrival_instructions=arrival_instructions,
        ),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


def _build_profile_no_office() -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="t-1",
        system_prompt="prompt",
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


class TestOfficeContextSection:
    def test_renders_virtual_constant_when_agent_profile_is_none(self) -> None:
        """Virtual instructions are always present; no office block without a profile."""
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        result = section.render(ctx, known_patient=None, agent_profile=None)
        joined = "\n".join(result)
        assert "Datos del consultorio" in joined
        assert booking_constants.VIRTUAL_SESSION_BOT_INSTRUCTIONS in joined
        assert "Dirección" not in joined

    def test_always_renders_virtual_instructions_constant(self) -> None:
        """Virtual instructions are always shown regardless of office_location."""
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_no_office()
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Datos del consultorio" in joined
        assert booking_constants.VIRTUAL_SESSION_BOT_INSTRUCTIONS in joined
        assert "Dirección" not in joined

    def test_renders_office_location_with_all_fields(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_with_office()
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Datos del consultorio" in joined
        assert "Calle 5 # 38-25, Cali" in joined
        assert "Llegar 20 min antes" in joined
        assert booking_constants.VIRTUAL_SESSION_BOT_INSTRUCTIONS in joined

    def test_renders_office_location_without_optional_fields(self) -> None:
        section = office_context_section.OfficeContextSection()
        ctx = _build_context()
        profile = _build_profile_with_office(arrival_instructions=None)
        result = section.render(ctx, known_patient=None, agent_profile=profile)
        joined = "\n".join(result)
        assert "Calle 5 # 38-25, Cali" in joined
        assert "Indicaciones" not in joined
        assert booking_constants.VIRTUAL_SESSION_BOT_INSTRUCTIONS in joined
