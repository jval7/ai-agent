import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.conversation_dto as conversation_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class ConversationControlService:
    def __init__(
        self,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._scheduling_repository = scheduling_repository
        self._clock = clock

    def update_control_mode(
        self,
        claims: auth_dto.TokenClaimsDTO,
        conversation_id: str,
        update_dto: conversation_dto.UpdateConversationControlModeDTO,
    ) -> conversation_dto.ConversationControlModeResponseDTO:
        self._ensure_owner(claims)

        conversation = self._conversation_repository.get_conversation_by_id(
            claims.tenant_id,
            conversation_id,
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        now_value = self._clock.now()
        conversation.set_control_mode(update_dto.control_mode, now_value)
        self._conversation_repository.save_conversation(conversation)
        logger.info(
            "conversation.control_mode_changed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="conversation.control_mode_changed",
                    message="conversation control mode changed",
                    data={
                        "tenant_id": conversation.tenant_id,
                        "conversation_id": conversation.id,
                        "control_mode": conversation.control_mode,
                    },
                )
            },
        )

        return conversation_dto.ConversationControlModeResponseDTO(
            conversation_id=conversation.id,
            tenant_id=conversation.tenant_id,
            control_mode=conversation.control_mode,
            updated_at=conversation.updated_at,
        )

    def reset_messages(
        self,
        claims: auth_dto.TokenClaimsDTO,
        conversation_id: str,
    ) -> None:
        self._ensure_owner(claims)

        conversation = self._conversation_repository.get_conversation_by_id(
            claims.tenant_id,
            conversation_id,
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        now_value = self._clock.now()
        scheduling_requests = self._scheduling_repository.list_requests_by_conversation(
            claims.tenant_id,
            conversation_id,
        )
        cancelled_request_ids: list[str] = []
        for request in scheduling_requests:
            if request.status in (
                "AWAITING_CONSULTATION_REVIEW",
                "AWAITING_CONSULTATION_DETAILS",
                "COLLECTING_PREFERENCES",
                "AWAITING_PROFESSIONAL_SLOTS",
                "AWAITING_PATIENT_CHOICE",
            ):
                request.professional_note = "conversation reset by owner"
                request.set_status("CANCELLED", now_value)
                self._scheduling_repository.save_request(request)
                cancelled_request_ids.append(request.id)

        conversation.message_ids = []
        conversation.messages = []
        conversation.last_message_preview = None
        conversation.updated_at = now_value
        self._conversation_repository.save_conversation(conversation)
        self._conversation_repository.delete_messages(claims.tenant_id, conversation_id)
        logger.info(
            "conversation.messages_reset",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="conversation.messages_reset",
                    message="conversation messages reset by owner",
                    data={
                        "tenant_id": conversation.tenant_id,
                        "conversation_id": conversation.id,
                        "cancelled_scheduling_requests_count": len(cancelled_request_ids),
                    },
                )
            },
        )

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")
