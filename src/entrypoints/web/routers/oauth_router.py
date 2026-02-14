import fastapi
import fastapi.responses as fastapi_responses

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.exceptions as service_exceptions

router = fastapi.APIRouter(tags=["oauth"])


def _resolve_status_code(error: service_exceptions.ServiceError) -> int:
    if isinstance(error, service_exceptions.EntityNotFoundError):
        return 404
    if isinstance(error, service_exceptions.InvalidStateError):
        return 400
    if isinstance(error, service_exceptions.ExternalProviderError):
        return 502
    if isinstance(error, service_exceptions.AuthorizationError):
        return 403
    if isinstance(error, service_exceptions.AuthenticationError):
        return 401
    return 400


@router.get("/oauth/meta/callback", response_class=fastapi_responses.HTMLResponse)
def meta_oauth_callback(
    code: str,
    state: str,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> fastapi_responses.HTMLResponse:
    try:
        connection_status = container.whatsapp_onboarding_service.complete_embedded_signup_by_state(
            code=code,
            state=state,
        )
    except service_exceptions.ServiceError as error:
        status_code = _resolve_status_code(error)
        return fastapi_responses.HTMLResponse(
            status_code=status_code,
            content=(
                f"<html><body><h2>WhatsApp Connection Failed</h2><p>{error!s}</p></body></html>"
            ),
        )

    return fastapi_responses.HTMLResponse(
        status_code=200,
        content=(
            "<html><body><h2>WhatsApp Connected Successfully</h2>"
            f"<p>Tenant: {connection_status.tenant_id}</p>"
            f"<p>Phone Number ID: {connection_status.phone_number_id}</p>"
            "<p>You can return to your app now.</p>"
            "</body></html>"
        ),
    )
