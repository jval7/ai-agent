import src.domain.booking_constants as booking_constants
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models


class OfficeContextSection(prompt_section.PromptSection):
    """Renders a 'Datos del consultorio' block.

    - The virtual session instructions are always included (product-wide constant).
    - The office address block is only rendered when AgentProfile has office_location.
    """

    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
        agent_profile: agent_profile_entity.AgentProfile | None = None,
    ) -> list[str]:
        del runtime_context
        del known_patient

        lines: list[str] = ["Datos del consultorio:"]

        if agent_profile is not None and agent_profile.office_location is not None:
            office = agent_profile.office_location
            lines.append(f"- Dirección: {office.address}")
            # Marker explicito cuando el campo opcional es None — sin esto el
            # LLM lee la seccion como "datos faltantes" y se va por la valvula
            # de escape "te contactara un asesor", quedando atorado en
            # POST_BOOKING_FOLLOWUP sin llamar close_session.
            if office.arrival_instructions is not None:
                lines.append(f"- Indicaciones de llegada: {office.arrival_instructions}")
            else:
                lines.append("- Indicaciones de llegada: (no provistas)")

        lines.append(
            f"- Instrucciones sesión virtual: {booking_constants.VIRTUAL_SESSION_BOT_INSTRUCTIONS}"
        )

        return lines
