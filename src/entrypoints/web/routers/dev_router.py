import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.dev_dto as dev_dto

router = fastapi.APIRouter(prefix="/v1/dev", tags=["dev"])


@router.post("/memory/reset", response_model=dev_dto.MemoryResetResponseDTO)
def reset_memory(
    _: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> dev_dto.MemoryResetResponseDTO:
    return container.memory_admin_service.reset_memory()
