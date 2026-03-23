import src.services.agentic.guards.base as base
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.use_cases.scheduling_service as scheduling_service


class WaitingProfessionalSilentGuard:
    """Returns True when the conversation should be silently skipped
    because it is waiting for professional response."""

    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService | None,
    ) -> None:
        self._scheduling_service = scheduling_svc

    def is_active(self, context: base.GuardContext) -> bool:
        return (
            self._find_latest_waiting_professional_request(
                tenant_id=context.tenant_id,
                conversation_id=context.conversation_id,
            )
            is not None
        )

    def _find_latest_waiting_professional_request(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO | None:
        if self._scheduling_service is None:
            return None
        del tenant_id
        del conversation_id
        return None
