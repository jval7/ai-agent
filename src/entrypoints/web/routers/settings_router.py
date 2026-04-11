import fastapi
import pydantic

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions

router = fastapi.APIRouter(prefix="/v1/settings", tags=["settings"])


class DevFeaturesResponse(pydantic.BaseModel):
    enabled: bool
    sandbox_enabled: bool | None


class SandboxResponse(pydantic.BaseModel):
    sandbox_enabled: bool


class SandboxUpdateRequest(pydantic.BaseModel):
    sandbox_enabled: bool


@router.get("/dev-features", response_model=DevFeaturesResponse)
def get_dev_features(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> DevFeaturesResponse:
    if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
        raise service_exceptions.AuthorizationError("professional role required")
    if not container.settings.enable_dev_endpoints:
        return DevFeaturesResponse(enabled=False, sandbox_enabled=None)
    return DevFeaturesResponse(
        enabled=True,
        sandbox_enabled=container.settings.whatsapp_outbound_noop,
    )


@router.put(
    "/sandbox",
    response_model=SandboxResponse,
    dependencies=[fastapi.Depends(http_dependencies.require_dev_endpoints)],
)
def update_sandbox_mode(
    body: SandboxUpdateRequest,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> SandboxResponse:
    if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
        raise service_exceptions.AuthorizationError("professional role required")
    container.settings.whatsapp_outbound_noop = body.sandbox_enabled
    return SandboxResponse(sandbox_enabled=container.settings.whatsapp_outbound_noop)
