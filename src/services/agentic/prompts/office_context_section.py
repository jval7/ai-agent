import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models


class OfficeContextSection(prompt_section.PromptSection):
    """Renders a 'Datos del consultorio' block when the AgentProfile has
    office_location or virtual_session_instructions configured."""

    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
        agent_profile: agent_profile_entity.AgentProfile | None = None,
    ) -> list[str]:
        del runtime_context
        del known_patient
        if agent_profile is None:
            return []

        has_office = agent_profile.office_location is not None
        has_virtual = agent_profile.virtual_session_instructions is not None

        if not has_office and not has_virtual:
            return []

        lines: list[str] = ["Datos del consultorio:"]

        if has_office:
            office = agent_profile.office_location
            assert office is not None
            lines.append(f"- Dirección: {office.address}")
            if office.arrival_instructions is not None:
                lines.append(f"- Indicaciones de llegada: {office.arrival_instructions}")
            if office.access_notes is not None:
                lines.append(f"- Notas de acceso: {office.access_notes}")

        if has_virtual:
            lines.append(
                f"- Instrucciones sesión virtual: {agent_profile.virtual_session_instructions}"
            )

        return lines
