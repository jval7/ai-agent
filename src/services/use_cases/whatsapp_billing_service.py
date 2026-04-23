import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.whatsapp_billing_dto as whatsapp_billing_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class WhatsappBillingService:
    def __init__(
        self,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._whatsapp_provider = whatsapp_provider
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._agent_profile_repository = agent_profile_repository
        self._clock = clock

    def run_preflight(
        self,
        tenant_id: str,
        request: whatsapp_billing_dto.BillingPreflightRequestDTO,
    ) -> whatsapp_billing_dto.BillingPreflightResponseDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("whatsapp connection not found")
        if connection.status != "CONNECTED":
            raise service_exceptions.InvalidStateError(
                "whatsapp connection is not in CONNECTED state"
            )
        if connection.access_token is None or connection.phone_number_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")

        try:
            self._whatsapp_provider.send_hello_world_preflight(
                access_token=connection.access_token,
                phone_number_id=connection.phone_number_id,
                recipient_phone_e164=request.recipient_phone_number,
            )
        except service_exceptions.WhatsappBillingNotConfiguredError:
            logger.info(
                "whatsapp.billing.preflight.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.billing.preflight.failed",
                        message="billing preflight rejected by meta (no payment method)",
                        data={
                            "tenant_id": tenant_id,
                            "meta_error_code": 131042,
                        },
                    )
                },
            )
            raise
        except service_exceptions.WhatsappPreflightError as error:
            logger.info(
                "whatsapp.billing.preflight.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="whatsapp.billing.preflight.failed",
                        message="billing preflight failed",
                        data={
                            "tenant_id": tenant_id,
                            "meta_error_code": error.meta_error_code,
                        },
                    )
                },
            )
            raise

        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is not None:
            agent_profile.reminder_billing_test_phone_number = request.recipient_phone_number
            agent_profile.updated_at = self._clock.now()
            self._agent_profile_repository.save(agent_profile)

        logger.info(
            "whatsapp.billing.preflight.success",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.billing.preflight.success",
                    message="billing preflight succeeded",
                    data={
                        "tenant_id": tenant_id,
                        "recipient_phone_number": request.recipient_phone_number,
                    },
                )
            },
        )

        return whatsapp_billing_dto.BillingPreflightResponseDTO(
            ok=True,
            recipient_phone_number=request.recipient_phone_number,
        )
