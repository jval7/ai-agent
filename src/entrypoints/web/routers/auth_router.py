import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto

router = fastapi.APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/register", response_model=auth_dto.AuthTokensDTO)
def register(
    register_dto: auth_dto.RegisterUserDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.AuthTokensDTO:
    return container.auth_service.register(register_dto)


@router.post("/login", response_model=auth_dto.AuthTokensDTO)
def login(
    login_dto: auth_dto.LoginDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.AuthTokensDTO:
    return container.auth_service.login(login_dto)


@router.post("/refresh", response_model=auth_dto.AuthTokensDTO)
def refresh(
    refresh_dto: auth_dto.RefreshTokenDTO,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> auth_dto.AuthTokensDTO:
    return container.auth_service.refresh(refresh_dto)


@router.post("/logout", status_code=204)
def logout(
    logout_dto: auth_dto.LogoutDTO,
    _: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.auth_service.logout(logout_dto)
    return None
