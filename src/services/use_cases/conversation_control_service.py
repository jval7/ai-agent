import src.domain.entities.message as message_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
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
        patient_repository: patient_repository_port.PatientRepositoryPort,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._scheduling_repository = scheduling_repository
        self._patient_repository = patient_repository
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._whatsapp_provider = whatsapp_provider
        self._id_generator = id_generator
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

        scheduling_requests = self._scheduling_repository.list_requests_by_conversation(
            claims.tenant_id,
            conversation_id,
        )
        deleted_request_ids: list[str] = []
        for request in scheduling_requests:
            self._scheduling_repository.delete_request(claims.tenant_id, request.id)
            deleted_request_ids.append(request.id)

        self._patient_repository.delete(claims.tenant_id, conversation.whatsapp_user_id)
        self._conversation_repository.delete_messages(claims.tenant_id, conversation_id)
        self._conversation_repository.delete_whatsapp_user(
            claims.tenant_id, conversation.whatsapp_user_id
        )
        self._conversation_repository.delete_conversation(claims.tenant_id, conversation_id)
        logger.info(
            "conversation.fully_reset",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="conversation.fully_reset",
                    message="conversation fully reset by owner",
                    data={
                        "tenant_id": conversation.tenant_id,
                        "conversation_id": conversation.id,
                        "whatsapp_user_id": conversation.whatsapp_user_id,
                        "deleted_scheduling_requests_count": len(deleted_request_ids),
                    },
                )
            },
        )

    def send_professional_message(
        self,
        claims: auth_dto.TokenClaimsDTO,
        conversation_id: str,
        send_dto: conversation_dto.SendProfessionalMessageDTO,
    ) -> conversation_dto.MessageSentResponseDTO:
        self._ensure_owner(claims)

        conversation = self._conversation_repository.get_conversation_by_id(
            claims.tenant_id,
            conversation_id,
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")
        if conversation.control_mode != "HUMAN":
            raise service_exceptions.InvalidStateError(
                "conversation must be in HUMAN mode to send messages"
            )

        connection = self._whatsapp_connection_repository.get_by_tenant_id(claims.tenant_id)
        if (
            connection is None
            or connection.access_token is None
            or connection.phone_number_id is None
        ):
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")

        provider_message_id = self._whatsapp_provider.send_text_message(
            access_token=connection.access_token,
            phone_number_id=connection.phone_number_id,
            whatsapp_user_id=conversation.whatsapp_user_id,
            text=send_dto.message_text,
        )

        now_value = self._clock.now()
        outbound_message = message_entity.Message(
            id=self._id_generator.new_id(),
            conversation_id=conversation_id,
            tenant_id=claims.tenant_id,
            direction="OUTBOUND",
            role="human_agent",
            content=send_dto.message_text,
            provider_message_id=provider_message_id,
            created_at=now_value,
        )
        self._conversation_repository.save_message(outbound_message)
        conversation.append_message(
            outbound_message.id,
            outbound_message.content,
            now_value,
        )
        self._conversation_repository.save_conversation(conversation)

        logger.info(
            "conversation.professional_message_sent",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="conversation.professional_message_sent",
                    message="professional sent message to patient",
                    data={
                        "tenant_id": claims.tenant_id,
                        "conversation_id": conversation_id,
                    },
                )
            },
        )

        return conversation_dto.MessageSentResponseDTO(
            message_id=outbound_message.id,
            conversation_id=conversation_id,
            role="human_agent",
            content=outbound_message.content,
            created_at=outbound_message.created_at,
        )

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")
