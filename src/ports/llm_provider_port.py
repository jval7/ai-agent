import abc

import src.services.dto.llm_dto as llm_dto


class LlmProviderPort(abc.ABC):
    @abc.abstractmethod
    def generate_reply(self, prompt_input: llm_dto.GenerateReplyInputDTO) -> llm_dto.AgentReplyDTO:
        raise NotImplementedError
