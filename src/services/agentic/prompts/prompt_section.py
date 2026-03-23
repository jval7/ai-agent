import abc

import src.domain.entities.patient as patient_entity
import src.services.agentic.state_models as agentic_state_models


class PromptSection(abc.ABC):
    @abc.abstractmethod
    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
    ) -> list[str]:
        raise NotImplementedError
