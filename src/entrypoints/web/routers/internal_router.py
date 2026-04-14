import fastapi
import pydantic

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container

router = fastapi.APIRouter(prefix="/v1/internal", tags=["internal"])


class AutoCloseRequestBody(pydantic.BaseModel):
    tenant_id: str


@router.post("/scheduling-requests/{scheduling_request_id}/auto-close")
def auto_close_booked_session(
    scheduling_request_id: str,
    body: AutoCloseRequestBody,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> dict[str, str]:
    # TODO: implementar validación OIDC token para verificar identidad del service account
    return container.scheduling_service.auto_close_booked_request(
        tenant_id=body.tenant_id,
        scheduling_request_id=scheduling_request_id,
    )


class ExecuteReminderRequestBody(pydantic.BaseModel):
    tenant_id: str


@router.post("/reminders/{reminder_id}/execute")
def execute_appointment_reminder(
    reminder_id: str,
    body: ExecuteReminderRequestBody,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> dict[str, str]:
    return container.reminder_service.execute_reminder(
        tenant_id=body.tenant_id,
        reminder_id=reminder_id,
    )
