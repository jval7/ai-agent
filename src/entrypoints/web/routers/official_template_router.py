import fastapi

import src.domain.official_reminder_templates as official_reminder_templates
import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto

router = fastapi.APIRouter(
    prefix="/v1/whatsapp/templates/official",
    tags=["whatsapp-templates-official"],
)


@router.get("/status", response_model=whatsapp_template_dto.OfficialTemplateListDTO)
def list_official_template_status(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_template_dto.OfficialTemplateListDTO:
    return container.whatsapp_template_service.list_official_template_status(claims.tenant_id)


@router.post(
    "/{kind}/activate",
    response_model=whatsapp_template_dto.OfficialTemplateStatusDTO,
    status_code=200,
)
def activate_official_template(
    kind: official_reminder_templates.OfficialReminderKind,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> whatsapp_template_dto.OfficialTemplateStatusDTO:
    return container.whatsapp_template_service.activate_official_template(
        tenant_id=claims.tenant_id,
        kind=kind,
    )


@router.post("/{kind}/deactivate", status_code=204)
def deactivate_official_template(
    kind: official_reminder_templates.OfficialReminderKind,
    hard: bool = False,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.whatsapp_template_service.deactivate_official_template(
        tenant_id=claims.tenant_id,
        kind=kind,
        hard=hard,
    )
