import pydantic


class ChatMessageDTO(pydantic.BaseModel):
    role: str
    content: str


class GenerateReplyInputDTO(pydantic.BaseModel):
    system_prompt: str
    messages: list[ChatMessageDTO]


class AgentReplyDTO(pydantic.BaseModel):
    content: str
