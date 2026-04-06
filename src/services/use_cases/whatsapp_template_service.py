import src.infra.logs as app_logs
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class WhatsappTemplateService:
    def __init__(
        self,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
    ) -> None:
        self._whatsapp_provider = whatsapp_provider
        self._whatsapp_connection_repository = whatsapp_connection_repository

    def list_templates(self, tenant_id: str) -> whatsapp_template_dto.TemplateListDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("whatsapp connection not found")
        if connection.status != "CONNECTED":
            raise service_exceptions.InvalidStateError(
                "whatsapp connection is not in CONNECTED state"
            )
        if connection.access_token is None or connection.business_account_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")
        templates = self._whatsapp_provider.list_message_templates(
            access_token=connection.access_token,
            waba_id=connection.business_account_id,
        )
        logger.info(
            "whatsapp.templates.listed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.templates.listed",
                    message="templates listed",
                    data={"tenant_id": tenant_id, "count": len(templates)},
                )
            },
        )
        return whatsapp_template_dto.TemplateListDTO(templates=templates)

    def create_template(
        self, tenant_id: str, request: whatsapp_template_dto.CreateTemplateRequestDTO
    ) -> whatsapp_template_dto.TemplateDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("whatsapp connection not found")
        if connection.status != "CONNECTED":
            raise service_exceptions.InvalidStateError(
                "whatsapp connection is not in CONNECTED state"
            )
        if connection.access_token is None or connection.business_account_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")
        template = self._whatsapp_provider.create_message_template(
            access_token=connection.access_token,
            waba_id=connection.business_account_id,
            template=request,
        )
        logger.info(
            "whatsapp.templates.created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.templates.created",
                    message="template created",
                    data={
                        "tenant_id": tenant_id,
                        "template_name": request.name,
                        "template_id": template.id,
                    },
                )
            },
        )
        return template

    def delete_template(self, tenant_id: str, template_name: str) -> None:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("whatsapp connection not found")
        if connection.status != "CONNECTED":
            raise service_exceptions.InvalidStateError(
                "whatsapp connection is not in CONNECTED state"
            )
        if connection.access_token is None or connection.business_account_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")
        self._whatsapp_provider.delete_message_template(
            access_token=connection.access_token,
            waba_id=connection.business_account_id,
            template_name=template_name,
        )
        logger.info(
            "whatsapp.templates.deleted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.templates.deleted",
                    message="template deleted",
                    data={"tenant_id": tenant_id, "template_name": template_name},
                )
            },
        )
