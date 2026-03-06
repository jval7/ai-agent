import abc

import src.services.agentic.state_models as agentic_state_models
import src.services.dto.agent_workflow_dto as agent_workflow_dto


class ConversationWorkflowRuntimePort(abc.ABC):
    @abc.abstractmethod
    def load_runtime_prompt_context(self) -> agentic_state_models.RuntimePromptContext:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_waiting_patient_choice_override(self) -> str | None:
        raise NotImplementedError

    @abc.abstractmethod
    def enforce_required_numeric_slot_selection(self) -> str | None:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_waiting_professional_override(self) -> str | None:
        raise NotImplementedError

    @abc.abstractmethod
    def is_waiting_professional_state_active(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def build_runtime_prompt_preview(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
    ) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def generate_reply_with_tools(self) -> str:
        raise NotImplementedError


class SchedulingTransitionRuntimePort(abc.ABC):
    @abc.abstractmethod
    def validate_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def apply_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
    ) -> object:
        raise NotImplementedError

    @abc.abstractmethod
    def execute_side_effects(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def persist_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def build_output(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> object:
        raise NotImplementedError


class AgentWorkflowPort(abc.ABC):
    @abc.abstractmethod
    def run_conversation_flow(
        self,
        input_dto: agent_workflow_dto.ConversationWorkflowInputDTO,
        runtime_port: ConversationWorkflowRuntimePort,
    ) -> agent_workflow_dto.ConversationWorkflowResultDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def run_scheduling_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        runtime_port: SchedulingTransitionRuntimePort,
    ) -> agent_workflow_dto.SchedulingTransitionResultDTO:
        raise NotImplementedError
