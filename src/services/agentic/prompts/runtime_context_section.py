import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models
import src.services.scheduling_slot_formatter as scheduling_slot_formatter

_FALLBACK_TIMEZONE = "America/Bogota"


def _resolve_timezone(agent_profile: agent_profile_entity.AgentProfile | None) -> str:
    """Return the tenant's configured timezone, falling back to America/Bogota."""
    if agent_profile is None:
        return _FALLBACK_TIMEZONE
    if agent_profile.identity is None:
        return _FALLBACK_TIMEZONE
    return agent_profile.identity.timezone or _FALLBACK_TIMEZONE


class RuntimeContextSection(prompt_section.PromptSection):
    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
        agent_profile: agent_profile_entity.AgentProfile | None = None,
    ) -> list[str]:
        del known_patient
        timezone_name = _resolve_timezone(agent_profile)
        lines = [
            "INSTRUCCIONES RUNTIME (PRIORIDAD ALTA):",
            f"- estado_conversacion: {runtime_context.state}",
        ]
        if runtime_context.request_id is not None:
            lines.append(f"- request_id_activo: {runtime_context.request_id}")
        if runtime_context.request_status is not None:
            lines.append(f"- request_status_activo: {runtime_context.request_status}")
        if runtime_context.appointment_modality is not None:
            lines.append(f"- modalidad_actual: {runtime_context.appointment_modality}")
        if runtime_context.patient_location is not None:
            lines.append(f"- ubicacion_actual: {runtime_context.patient_location}")
        if runtime_context.patient_preference_note is not None:
            lines.append(f"- preferencia_horaria_actual: {runtime_context.patient_preference_note}")
        if runtime_context.selected_slot_id is not None:
            lines.append(f"- slot_seleccionado_actual: {runtime_context.selected_slot_id}")
        if runtime_context.appointment_start_at is not None:
            lines.append(
                "- fecha_cita: "
                + scheduling_slot_formatter.format_appointment_natural(
                    start_at=runtime_context.appointment_start_at,
                    end_at=runtime_context.appointment_end_at,
                    timezone_name=timezone_name,
                )
            )
        if runtime_context.patient_first_name is not None:
            lines.append(f"- nombre_paciente: {runtime_context.patient_first_name}")
        if runtime_context.professional_note is not None:
            lines.append(
                "Notas del profesional para este paso (si existen, siguela al pedir datos): "
                f"{runtime_context.professional_note}"
            )
        return lines
