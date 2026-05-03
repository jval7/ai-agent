import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models
import src.services.scheduling_slot_formatter as scheduling_slot_formatter

_FALLBACK_TIMEZONE = "America/Bogota"

# El nombre canonico del estado (en el codigo, en Firestore y en los DTOs)
# contiene la palabra "CONFIRMATION" por razones historicas. Pero proyectar
# ese nombre literal en el system prompt satura la attention del LLM con el
# concepto "confirmation" y lo hace generar slips como "para confirmarte la
# cita" / "confirmar tu reserva" en pre-pago, violando uses_pre_payment_vocabulary.
#
# Para reducir esa saturacion sin tocar persistence, este modulo proyecta un
# ALIAS visible al LLM mientras el codigo interno sigue usando el nombre
# canonico. La traduccion es solo en lectura (rendering) — los entries que
# se persisten o se comparan en el codigo no cambian.
#
# AWAITING_ATTENDANCE_CONFIRMATION queda IGUAL: ese estado SI es legitimo de
# confirmacion (post-pago, recordatorio: el paciente confirma su asistencia).
_LLM_VISIBLE_STATE_ALIASES: dict[str, str] = {
    "AWAITING_PAYMENT_CONFIRMATION": "AWAITING_PAYMENT_RECEIPT",
    "COLLECTING_CONFIRMATION_DATA": "COLLECTING_FINAL_DATA",
}


def _llm_visible_state_name(canonical_name: str) -> str:
    """Return the alias projected to the LLM for a canonical state name."""
    return _LLM_VISIBLE_STATE_ALIASES.get(canonical_name, canonical_name)


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
            f"- estado_conversacion: {_llm_visible_state_name(runtime_context.state)}",
        ]
        if runtime_context.request_id is not None:
            lines.append(f"- request_id_activo: {runtime_context.request_id}")
        if runtime_context.request_status is not None:
            lines.append(
                f"- request_status_activo: {_llm_visible_state_name(runtime_context.request_status)}"
            )
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
