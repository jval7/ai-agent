import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.entrypoints.web.rate_limiter as rate_limiter
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto

router = fastapi.APIRouter(prefix="/v1/auth", tags=["auth"])

_NO_CONTENT = 204


@router.get("/me", response_model=auth_dto.MeResponseDTO)
def get_me(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.MeResponseDTO:
    user = container.auth_service.get_user_by_id(claims.sub)
    if user is None:
        raise fastapi.HTTPException(status_code=404, detail="user not found")
    return auth_dto.MeResponseDTO(
        user_id=claims.sub,
        email=user.email,
        role=claims.role,
        tenant_id=claims.tenant_id,
    )


@router.post("/login", response_model=auth_dto.AuthTokensDTO)
@rate_limiter.limiter.limit("5/minute")  # type: ignore[misc,unused-ignore]
def login(
    request: fastapi.Request,
    login_dto: auth_dto.LoginDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.AuthTokensDTO:
    return container.auth_service.login(login_dto)


@router.post("/refresh", response_model=auth_dto.AuthTokensDTO)
@rate_limiter.limiter.limit("10/minute")  # type: ignore[misc,unused-ignore]
def refresh(
    request: fastapi.Request,
    refresh_dto: auth_dto.RefreshTokenDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.AuthTokensDTO:
    return container.auth_service.refresh(refresh_dto)


@router.post("/logout", status_code=204)
@rate_limiter.limiter.limit("10/minute")  # type: ignore[misc,unused-ignore]
def logout(
    request: fastapi.Request,
    logout_dto: auth_dto.LogoutDTO,
    _: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.auth_service.logout(logout_dto)
    return None


@router.post("/accept-invite", response_model=auth_dto.AuthTokensDTO)
@rate_limiter.limiter.limit("5/minute")  # type: ignore[misc,unused-ignore]
def accept_invite(
    request: fastapi.Request,
    accept_dto: auth_dto.AcceptInvitationDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.AuthTokensDTO:
    return container.invitation_service.accept_account_setup(
        token=accept_dto.token,
        new_password=accept_dto.new_password,
    )


@router.post("/password-reset/request", status_code=_NO_CONTENT)
@rate_limiter.limiter.limit("3/minute")  # type: ignore[misc,unused-ignore]
def request_password_reset(
    request: fastapi.Request,
    reset_dto: auth_dto.RequestPasswordResetDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.invitation_service.request_password_reset(email=reset_dto.email)
    return None


@router.post("/password-reset/confirm", status_code=_NO_CONTENT)
@rate_limiter.limiter.limit("5/minute")  # type: ignore[misc,unused-ignore]
def confirm_password_reset(
    request: fastapi.Request,
    confirm_dto: auth_dto.ConfirmPasswordResetDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.invitation_service.confirm_password_reset(
        token=confirm_dto.token,
        new_password=confirm_dto.new_password,
    )
    return None
