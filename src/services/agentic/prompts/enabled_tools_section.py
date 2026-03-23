import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models


class EnabledToolsSection(prompt_section.PromptSection):
    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
    ) -> list[str]:
        del known_patient
        return [
            "Tools habilitadas en este turno (usa solo estas y ninguna otra): "
            + ", ".join(runtime_context.enabled_tool_names)
        ]
