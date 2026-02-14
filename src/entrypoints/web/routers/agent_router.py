import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.agent_dto as agent_dto
import src.services.dto.auth_dto as auth_dto

router = fastapi.APIRouter(prefix="/v1/agent", tags=["agent"])


@router.get("/system-prompt", response_model=agent_dto.SystemPromptResponseDTO)
def get_system_prompt(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> agent_dto.SystemPromptResponseDTO:
    return container.agent_service.get_system_prompt(claims.tenant_id)


@router.put("/system-prompt", response_model=agent_dto.SystemPromptResponseDTO)
def update_system_prompt(
    update_dto: agent_dto.UpdateSystemPromptDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> agent_dto.SystemPromptResponseDTO:
    return container.agent_service.update_system_prompt(claims.tenant_id, update_dto)
