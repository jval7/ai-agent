import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.conversation_dto as conversation_dto

router = fastapi.APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.get("", response_model=conversation_dto.ConversationListResponseDTO)
def list_conversations(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> conversation_dto.ConversationListResponseDTO:
    return container.conversation_query_service.list_conversations(claims.tenant_id)


@router.get("/{conversation_id}/messages", response_model=conversation_dto.MessageListResponseDTO)
def list_messages(
    conversation_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> conversation_dto.MessageListResponseDTO:
    return container.conversation_query_service.list_messages(claims.tenant_id, conversation_id)


@router.put(
    "/{conversation_id}/control-mode",
    response_model=conversation_dto.ConversationControlModeResponseDTO,
)
def update_control_mode(
    conversation_id: str,
    update_dto: conversation_dto.UpdateConversationControlModeDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> conversation_dto.ConversationControlModeResponseDTO:
    return container.conversation_control_service.update_control_mode(
        claims=claims,
        conversation_id=conversation_id,
        update_dto=update_dto,
    )
