import src.ports.conversation_repository_port as conversation_repository_port
import src.services.agentic.tool_handlers.base as base
import src.services.dto.conversation_dto as conversation_dto
import src.services.dto.llm_dto as llm_dto


class SetContactNameHandler(base.ToolHandler):
    def __init__(
        self,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
    ) -> None:
        self._conversation_repository = conversation_repository

    def tool_name(self) -> str:
        return "set_contact_name"

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        validated_input = conversation_dto.SetContactNameToolInputDTO.model_validate(
            function_call.args
        )
        whatsapp_user = self._conversation_repository.get_whatsapp_user(
            context.tenant_id,
            context.whatsapp_user_id,
        )
        if whatsapp_user is not None:
            updated_user = whatsapp_user.model_copy(
                update={"display_name": validated_input.contact_name}
            )
            self._conversation_repository.save_whatsapp_user(updated_user)
        return {"status": "ok"}
