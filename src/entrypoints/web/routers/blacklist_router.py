import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.blacklist_dto as blacklist_dto

router = fastapi.APIRouter(prefix="/v1/blacklist", tags=["blacklist"])


@router.get("", response_model=blacklist_dto.BlacklistListResponseDTO)
def list_blacklist(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> blacklist_dto.BlacklistListResponseDTO:
    return container.blacklist_service.list_entries(claims)


@router.post("", response_model=blacklist_dto.BlacklistEntryDTO)
def upsert_blacklist_entry(
    upsert_dto: blacklist_dto.UpsertBlacklistEntryDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> blacklist_dto.BlacklistEntryDTO:
    return container.blacklist_service.upsert_entry(claims, upsert_dto)


@router.delete("/{whatsapp_user_id}", status_code=204)
def delete_blacklist_entry(
    whatsapp_user_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.blacklist_service.delete_entry(claims, whatsapp_user_id)
    return None
