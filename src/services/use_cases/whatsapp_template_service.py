import src.domain.official_reminder_templates as official_reminder_templates
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.reminder_service_port as reminder_service_port
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
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        clock: clock_port.ClockPort,
        reminder_service: reminder_service_port.ReminderServicePort,
    ) -> None:
        self._whatsapp_provider = whatsapp_provider
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._agent_profile_repository = agent_profile_repository
        self._clock = clock
        self._reminder_service = reminder_service

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
        # Guard: reject deletion of an activated official template.
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is not None:
            activated_names: set[str] = set()
            if agent_profile.appointment_reminder_attendance_template_name is not None:
                activated_names.add(agent_profile.appointment_reminder_attendance_template_name)
            if agent_profile.appointment_reminder_payment_template_name is not None:
                activated_names.add(agent_profile.appointment_reminder_payment_template_name)
            if template_name in activated_names:
                raise service_exceptions.OfficialTemplateActiveError(
                    f"template '{template_name}' is an activated official template; "
                    "deactivate it from Settings before deleting"
                )

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

    def activate_official_template(
        self,
        tenant_id: str,
        kind: official_reminder_templates.OfficialReminderKind,
    ) -> whatsapp_template_dto.OfficialTemplateStatusDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("whatsapp connection not found")
        if connection.status != "CONNECTED":
            raise service_exceptions.InvalidStateError(
                "whatsapp connection is not in CONNECTED state"
            )
        if connection.access_token is None or connection.business_account_id is None:
            raise service_exceptions.InvalidStateError("whatsapp connection is missing credentials")

        template_def = official_reminder_templates.get(kind)

        # Idempotent: if the template already exists in Meta, reuse its status
        # instead of re-submitting (Meta approval is slow; re-submission would
        # fail with "template already exists").
        existing_templates = self._whatsapp_provider.list_message_templates(
            access_token=connection.access_token,
            waba_id=connection.business_account_id,
        )
        existing = next((tpl for tpl in existing_templates if tpl.name == template_def.name), None)
        if existing is None:
            create_request = whatsapp_template_dto.CreateTemplateRequestDTO(
                name=template_def.name,
                category=template_def.category,
                language=template_def.language,
                components=[
                    whatsapp_template_dto.TemplateComponentDTO(
                        type="BODY",
                        text=template_def.body_text,
                        example_values=template_def.example_values,
                    )
                ],
            )
            created_status = self._whatsapp_provider.create_message_template(
                access_token=connection.access_token,
                waba_id=connection.business_account_id,
                template=create_request,
            ).status
        else:
            created_status = existing.status

        # Persist template name in AgentProfile.
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            raise service_exceptions.EntityNotFoundError("agent profile not found")

        now_value = self._clock.now()
        if kind == "ATTENDANCE":
            agent_profile.appointment_reminder_attendance_template_name = template_def.name
        else:
            agent_profile.appointment_reminder_payment_template_name = template_def.name
        agent_profile.updated_at = now_value
        self._agent_profile_repository.save(agent_profile)

        logger.info(
            "whatsapp.templates.official.activated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.templates.official.activated",
                    message="official template activated",
                    data={
                        "tenant_id": tenant_id,
                        "kind": kind,
                        "template_name": template_def.name,
                    },
                )
            },
        )

        meta_status = self._map_meta_status(created_status)
        return whatsapp_template_dto.OfficialTemplateStatusDTO(
            kind=kind,
            name=template_def.name,
            meta_status=meta_status,
            rejection_reason=None,
        )

    def deactivate_official_template(
        self,
        tenant_id: str,
        kind: official_reminder_templates.OfficialReminderKind,
    ) -> None:
        """Stops sending reminders for this kind without touching the Meta template.

        Cancels any pending Cloud Tasks so that scheduled reminders do not fire,
        but keeps the template name in the profile and the template in Meta. This
        enables a fast re-activation (no re-submission / re-approval) which is
        critical during testing since Meta approval can take minutes-to-hours.

        The caller (frontend) is responsible for setting
        ``appointment_reminder_enabled=False`` in the AgentProfile via
        ``update_agent_settings``.
        """
        template_def = official_reminder_templates.get(kind)

        # Cancel any pending reminders with this template name.
        self._reminder_service.cancel_reminders_by_template(tenant_id, template_def.name)

        logger.info(
            "whatsapp.templates.official.deactivated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="whatsapp.templates.official.deactivated",
                    message="official template deactivated (meta template preserved)",
                    data={"tenant_id": tenant_id, "kind": kind},
                )
            },
        )

    def list_official_template_status(
        self, tenant_id: str
    ) -> whatsapp_template_dto.OfficialTemplateListDTO:
        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("whatsapp connection not found")

        meta_templates_by_name: dict[str, whatsapp_template_dto.TemplateDTO] = {}
        if (
            connection.status == "CONNECTED"
            and connection.access_token is not None
            and connection.business_account_id is not None
        ):
            try:
                all_templates = self._whatsapp_provider.list_message_templates(
                    access_token=connection.access_token,
                    waba_id=connection.business_account_id,
                )
                for tpl in all_templates:
                    meta_templates_by_name[tpl.name] = tpl
            except service_exceptions.ExternalProviderError:
                logger.warning(
                    "whatsapp.templates.official.list_meta_failed",
                    extra={"tenant_id": tenant_id},
                    exc_info=True,
                )

        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)

        items: list[whatsapp_template_dto.OfficialTemplateStatusDTO] = []
        all_kinds: list[official_reminder_templates.OfficialReminderKind] = [
            "ATTENDANCE",
            "PAYMENT",
        ]
        for kind in all_kinds:
            template_def = official_reminder_templates.get(kind)

            # Determine whether a name was persisted in the profile.
            persisted_name: str | None = None
            if agent_profile is not None:
                if kind == "ATTENDANCE":
                    persisted_name = agent_profile.appointment_reminder_attendance_template_name
                else:
                    persisted_name = agent_profile.appointment_reminder_payment_template_name

            if persisted_name is None:
                items.append(
                    whatsapp_template_dto.OfficialTemplateStatusDTO(
                        kind=kind,
                        name=template_def.name,
                        meta_status="NOT_CREATED",
                        rejection_reason=None,
                    )
                )
                continue

            meta_tpl = meta_templates_by_name.get(persisted_name)
            if meta_tpl is None:
                items.append(
                    whatsapp_template_dto.OfficialTemplateStatusDTO(
                        kind=kind,
                        name=persisted_name,
                        meta_status="NOT_CREATED",
                        rejection_reason=None,
                    )
                )
            else:
                meta_status = self._map_meta_status(meta_tpl.status)
                items.append(
                    whatsapp_template_dto.OfficialTemplateStatusDTO(
                        kind=kind,
                        name=persisted_name,
                        meta_status=meta_status,
                        rejection_reason=None,
                    )
                )

        return whatsapp_template_dto.OfficialTemplateListDTO(items=items)

    def _map_meta_status(self, raw_status: str) -> whatsapp_template_dto.OfficialTemplateMetaStatus:
        normalized = raw_status.upper()
        valid: set[str] = {"PENDING", "APPROVED", "REJECTED", "DISABLED"}
        if normalized in valid:
            return normalized  # type: ignore[return-value]
        return "PENDING"
