import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto

router = fastapi.APIRouter(prefix="/v1/whatsapp/templates", tags=["whatsapp-templates"])


@router.get("", response_model=whatsapp_template_dto.TemplateListDTO)
def list_templates(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_template_dto.TemplateListDTO:
    return container.whatsapp_template_service.list_templates(claims.tenant_id)


@router.post("", response_model=whatsapp_template_dto.TemplateDTO)
def create_template(
    request: whatsapp_template_dto.CreateTemplateRequestDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_template_dto.TemplateDTO:
    return container.whatsapp_template_service.create_template(claims.tenant_id, request)


@router.delete("/{template_name}", status_code=204)
def delete_template(
    template_name: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.whatsapp_template_service.delete_template(claims.tenant_id, template_name)
