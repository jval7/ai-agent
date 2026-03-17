import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models


class PatientProfileSection(prompt_section.PromptSection):
    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
    ) -> list[str]:
        del runtime_context
        if known_patient is None:
            return ["- Known patient profile: not found"]

        known_patient_full_name = (
            _build_patient_full_name(
                first_name=known_patient.first_name,
                last_name=known_patient.last_name,
            )
            or known_patient.first_name
        )
        return [
            "Known patient profile (reuse this context and avoid asking repeated data):",
            f"- patient_full_name: {known_patient_full_name}",
            f"- patient_email: {known_patient.email}",
            f"- patient_age: {known_patient.age}",
            f"- consultation_reason: {known_patient.consultation_reason}",
            f"- patient_location: {known_patient.location}",
            f"- patient_phone: {known_patient.phone}",
            "If patient data is already known and still valid, do not ask for it again.",
        ]


def _build_patient_full_name(
    first_name: str | None,
    last_name: str | None,
) -> str | None:
    normalized_first = _normalize_text(first_name)
    normalized_last = _normalize_text(last_name)
    if normalized_first is None and normalized_last is None:
        return None
    if normalized_first is None:
        return normalized_last
    if normalized_last is None:
        return normalized_first
    return f"{normalized_first} {normalized_last}"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized
