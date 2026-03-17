import abc

import pydantic


class GuardContext(pydantic.BaseModel):
    tenant_id: str
    conversation_id: str
    whatsapp_user_id: str
    latest_user_text: str


class ConversationGuard(abc.ABC):
    """Base class for conversation guards.

    Guards evaluate the current conversation context and return either:
    - A terminal message (str) to short-circuit the conversation flow
    - None to continue to the next guard/LLM call
    """

    @abc.abstractmethod
    def evaluate(self, context: GuardContext) -> str | None:
        raise NotImplementedError
