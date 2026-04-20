import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.tenant_dto as tenant_dto
import src.services.exceptions as service_exceptions

router = fastapi.APIRouter(prefix="/v1/tenant", tags=["tenant"])


@router.get("/profile", response_model=tenant_dto.TenantProfileDTO)
def get_tenant_profile(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> tenant_dto.TenantProfileDTO:
    if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
        raise service_exceptions.AuthorizationError("professional role required")
    return container.tenant_profile_service.get_profile(claims.tenant_id)


@router.put("/profile", response_model=tenant_dto.TenantProfileDTO)
def update_tenant_profile(
    body: tenant_dto.UpdateTenantProfileDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> tenant_dto.TenantProfileDTO:
    if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
        raise service_exceptions.AuthorizationError("professional role required")
    return container.tenant_profile_service.update_profile(claims.tenant_id, body)
