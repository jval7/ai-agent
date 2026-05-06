import typing

import fastapi
import fastapi.security as fastapi_security

import src.infra.container as app_container
import src.infra.logs as app_logs
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions

bearer_scheme = fastapi_security.HTTPBearer(auto_error=False)


def get_container(request: fastapi.Request) -> app_container.AppContainer:
    return typing.cast(app_container.AppContainer, request.app.state.container)


def get_current_claims(
    credentials: fastapi_security.HTTPAuthorizationCredentials | None = fastapi.Depends(
        bearer_scheme
    ),
    container: app_container.AppContainer = fastapi.Depends(get_container),
) -> auth_dto.TokenClaimsDTO:
    if credentials is None:
        raise service_exceptions.AuthenticationError("missing bearer token")

    access_token = credentials.credentials
    claims = container.auth_service.authenticate_access_token(access_token)
    app_logs.set_authenticated_context(tenant_id=claims.tenant_id, user_id=claims.sub)
    return claims


def require_admin_claims(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(get_current_claims),
) -> auth_dto.TokenClaimsDTO:
    if claims.role != service_constants.ROLE_ADMIN:
        raise fastapi.HTTPException(status_code=403, detail="admin role required")
    return claims


def require_dev_endpoints(
    container: app_container.AppContainer = fastapi.Depends(get_container),
) -> None:
    if not container.settings.enable_dev_endpoints:
        raise service_exceptions.InvalidStateError("endpoint only available in dev environment")
