import pydantic


class ChatMessageDTO(pydantic.BaseModel):
    role: str
    content: str


class FunctionDeclarationDTO(pydantic.BaseModel):
    name: str
    description: str
    parameters_json_schema: dict[str, object]


class FunctionCallDTO(pydantic.BaseModel):
    name: str
    args: dict[str, object]
    call_id: str | None
    thought_signature: bytes | None = None


class FunctionResponseDTO(pydantic.BaseModel):
    name: str
    response: dict[str, object]
    call_id: str | None


class FunctionCallResultDTO(pydantic.BaseModel):
    function_call: FunctionCallDTO
    function_response: FunctionResponseDTO


class GenerateReplyInputDTO(pydantic.BaseModel):
    system_prompt: str
    messages: list[ChatMessageDTO]
    tools: list[FunctionDeclarationDTO] = pydantic.Field(default_factory=list)
    function_call_results: list[FunctionCallResultDTO] = pydantic.Field(default_factory=list)


class AgentReplyDTO(pydantic.BaseModel):
    content: str
    function_calls: list[FunctionCallDTO] = pydantic.Field(default_factory=list)
