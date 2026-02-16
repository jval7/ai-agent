import typing

import fastapi
import fastapi.security as fastapi_security

import src.infra.container as app_container
import src.infra.logs as app_logs
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
