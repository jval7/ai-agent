import datetime

import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.google_calendar_dto as google_calendar_dto

router = fastapi.APIRouter(prefix="/v1/google-calendar", tags=["google-calendar"])


@router.post("/oauth/session", response_model=google_calendar_dto.GoogleOauthSessionResponseDTO)
def create_oauth_session(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> google_calendar_dto.GoogleOauthSessionResponseDTO:
    return container.google_calendar_onboarding_service.create_oauth_session(
        tenant_id=claims.tenant_id,
        professional_user_id=claims.sub,
    )


@router.post(
    "/oauth/complete", response_model=google_calendar_dto.GoogleCalendarConnectionStatusDTO
)
def complete_oauth(
    complete_dto: google_calendar_dto.GoogleOauthCompleteDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
    return container.google_calendar_onboarding_service.complete_oauth(
        tenant_id=claims.tenant_id,
        professional_user_id=claims.sub,
        complete_dto=complete_dto,
    )


@router.get("/connection", response_model=google_calendar_dto.GoogleCalendarConnectionStatusDTO)
def get_connection(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
    return container.google_calendar_onboarding_service.get_connection_status(claims.tenant_id)


@router.get(
    "/availability", response_model=google_calendar_dto.GoogleCalendarAvailabilityResponseDTO
)
def get_availability(
    from_at: datetime.datetime = fastapi.Query(alias="from"),
    to_at: datetime.datetime = fastapi.Query(alias="to"),
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> google_calendar_dto.GoogleCalendarAvailabilityResponseDTO:
    return container.google_calendar_onboarding_service.get_availability(
        tenant_id=claims.tenant_id,
        from_at=from_at,
        to_at=to_at,
    )
