import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class WhatsappOnboardingService:
    def __init__(
        self,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        webhook_verify_token: str,
    ) -> None:
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._whatsapp_provider = whatsapp_provider
        self._id_generator = id_generator
        self._clock = clock
        self._webhook_verify_token = webhook_verify_token

    def create_embedded_signup_session(
        self, tenant_id: str
    ) -> whatsapp_dto.EmbeddedSignupSessionResponseDTO:
        now_value = self._clock.now()
        state_token = self._id_generator.new_token()
        existing_connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)

        connection = whatsapp_connection_entity.WhatsappConnection(
            tenant_id=tenant_id,
            phone_number_id=existing_connection.phone_number_id if existing_connection else None,
            business_account_id=existing_connection.business_account_id
            if existing_connection
            else None,
            access_token=existing_connection.access_token if existing_connection else None,
            status="PENDING",
            embedded_signup_state=state_token,
            updated_at=now_value,
        )
        self._whatsapp_connection_repository.save(connection)

        connect_url = self._whatsapp_provider.build_embedded_signup_url(state_token)
        logger.info(
            "whatsapp.onboarding.session_created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.onboarding.session_created",
                    message="embedded signup session created",
                    data={
                        "tenant_id": tenant_id,
                        "has_existing_connection": existing_connection is not None,
                    },
                )
            },
        )
        return whatsapp_dto.EmbeddedSignupSessionResponseDTO(
            state=state_token,
            connect_url=connect_url,
        )

    def complete_embedded_signup(
        self,
        tenant_id: str,
        complete_dto: whatsapp_dto.EmbeddedSignupCompleteDTO,
    ) -> whatsapp_dto.WhatsappConnectionStatusDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            logger.warning(
                "whatsapp.onboarding.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.onboarding.failed",
                        message="embedded signup completion failed",
                        data={
                            "tenant_id": tenant_id,
                            "reason": "session_not_found",
                        },
                    )
                },
            )
            raise service_exceptions.EntityNotFoundError("embedded signup session not found")

        if connection.embedded_signup_state != complete_dto.state:
            logger.warning(
                "whatsapp.onboarding.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.onboarding.failed",
                        message="embedded signup completion failed",
                        data={
                            "tenant_id": tenant_id,
                            "reason": "state_mismatch",
                        },
                    )
                },
            )
            raise service_exceptions.InvalidStateError("embedded signup state mismatch")

        credentials = self._whatsapp_provider.exchange_code_for_credentials(complete_dto.code)
        return self._finalize_connection(connection, credentials)

    def complete_embedded_signup_by_state(
        self, code: str, state: str
    ) -> whatsapp_dto.WhatsappConnectionStatusDTO:
        connection = self._whatsapp_connection_repository.get_by_embedded_signup_state(state)
        if connection is None:
            logger.warning(
                "whatsapp.onboarding.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.onboarding.failed",
                        message="embedded signup completion by state failed",
                        data={
                            "reason": "state_not_found",
                        },
                    )
                },
            )
            raise service_exceptions.EntityNotFoundError("embedded signup state not found")

        credentials = self._whatsapp_provider.exchange_code_for_credentials(code)
        return self._finalize_connection(connection, credentials)

    def _finalize_connection(
        self,
        connection: whatsapp_connection_entity.WhatsappConnection,
        credentials: whatsapp_dto.EmbeddedSignupCredentialsDTO,
    ) -> whatsapp_dto.WhatsappConnectionStatusDTO:
        now_value = self._clock.now()
        updated_connection = whatsapp_connection_entity.WhatsappConnection(
            tenant_id=connection.tenant_id,
            phone_number_id=credentials.phone_number_id,
            business_account_id=credentials.business_account_id,
            access_token=credentials.access_token,
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=now_value,
        )
        self._whatsapp_connection_repository.save(updated_connection)
        logger.info(
            "whatsapp.onboarding.completed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.onboarding.completed",
                    message="embedded signup completed",
                    data={
                        "tenant_id": updated_connection.tenant_id,
                        "status": updated_connection.status,
                        "has_phone_number_id": updated_connection.phone_number_id is not None,
                        "has_business_account_id": (
                            updated_connection.business_account_id is not None
                        ),
                    },
                )
            },
        )

        return whatsapp_dto.WhatsappConnectionStatusDTO(
            tenant_id=updated_connection.tenant_id,
            status=updated_connection.status,
            phone_number_id=updated_connection.phone_number_id,
            business_account_id=updated_connection.business_account_id,
        )

    def get_connection_status(self, tenant_id: str) -> whatsapp_dto.WhatsappConnectionStatusDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            return whatsapp_dto.WhatsappConnectionStatusDTO(
                tenant_id=tenant_id,
                status="DISCONNECTED",
                phone_number_id=None,
                business_account_id=None,
            )

        return whatsapp_dto.WhatsappConnectionStatusDTO(
            tenant_id=tenant_id,
            status=connection.status,
            phone_number_id=connection.phone_number_id,
            business_account_id=connection.business_account_id,
        )

    def get_dev_verify_token(self) -> whatsapp_dto.DevVerifyTokenDTO:
        if not self._webhook_verify_token:
            raise service_exceptions.InvalidStateError("META_WEBHOOK_VERIFY_TOKEN is required")

        return whatsapp_dto.DevVerifyTokenDTO(verify_token=self._webhook_verify_token)

    def verify_webhook(self, verification_dto: webhook_dto.WebhookVerificationDTO) -> str:
        if verification_dto.mode != "subscribe":
            logger.warning(
                "whatsapp.webhook.verify.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.webhook.verify.failed",
                        message="webhook verify failed",
                        data={"reason": "invalid_mode"},
                    )
                },
            )
            raise service_exceptions.AuthorizationError("invalid webhook mode")

        if not self._webhook_verify_token:
            logger.warning(
                "whatsapp.webhook.verify.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.webhook.verify.failed",
                        message="webhook verify failed",
                        data={"reason": "missing_verify_token"},
                    )
                },
            )
            raise service_exceptions.InvalidStateError("META_WEBHOOK_VERIFY_TOKEN is required")

        if verification_dto.verify_token != self._webhook_verify_token:
            logger.warning(
                "whatsapp.webhook.verify.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.webhook.verify.failed",
                        message="webhook verify failed",
                        data={"reason": "invalid_verify_token"},
                    )
                },
            )
            raise service_exceptions.AuthorizationError("invalid verify token")

        logger.info(
            "whatsapp.webhook.verify.succeeded",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.webhook.verify.succeeded",
                    message="webhook verify succeeded",
                )
            },
        )
        return verification_dto.challenge
