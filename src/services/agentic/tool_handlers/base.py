import abc

import pydantic

import src.services.dto.llm_dto as llm_dto


class ToolExecutionContext(pydantic.BaseModel):
    tenant_id: str
    conversation_id: str
    whatsapp_user_id: str


class ToolHandler(abc.ABC):
    @abc.abstractmethod
    def tool_name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def execute(
        self,
        context: ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        raise NotImplementedError
