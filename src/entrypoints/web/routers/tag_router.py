import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.tag_dto as tag_dto

router = fastapi.APIRouter(tags=["tags"])


@router.get("/v1/tags", response_model=tag_dto.TagListResponseDTO)
def list_tags(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> tag_dto.TagListResponseDTO:
    return container.tag_service.list_tags(claims)


@router.post("/v1/tags", response_model=tag_dto.TagDTO)
def create_tag(
    create_dto: tag_dto.CreateTagDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> tag_dto.TagDTO:
    return container.tag_service.create_custom_tag(claims, create_dto)


@router.put("/v1/tags/{tag_id}", response_model=tag_dto.TagDTO)
def update_tag(
    tag_id: str,
    update_dto: tag_dto.UpdateTagDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> tag_dto.TagDTO:
    return container.tag_service.update_tag(claims, tag_id, update_dto)


@router.delete("/v1/tags/{tag_id}", status_code=fastapi.status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.tag_service.delete_tag(claims, tag_id)


@router.post(
    "/v1/conversations/{conversation_id}/tags/{tag_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def assign_tag_to_conversation(
    conversation_id: str,
    tag_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.tag_service.assign_tag_to_conversation(claims, conversation_id, tag_id)


@router.delete(
    "/v1/conversations/{conversation_id}/tags/{tag_id}",
    status_code=fastapi.status.HTTP_204_NO_CONTENT,
)
def remove_tag_from_conversation(
    conversation_id: str,
    tag_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.tag_service.remove_tag_from_conversation(claims, conversation_id, tag_id)
