import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.scheduled_reminder_dto as scheduled_reminder_dto

router = fastapi.APIRouter(prefix="/v1/reminders", tags=["reminders"])


@router.get("", response_model=scheduled_reminder_dto.ScheduledReminderListResponseDTO)
def list_reminders(
    status: str | None = None,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> scheduled_reminder_dto.ScheduledReminderListResponseDTO:
    return container.reminder_service.list_reminders(claims.tenant_id, status)
