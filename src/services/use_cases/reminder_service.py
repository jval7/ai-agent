import datetime
import typing
import zoneinfo

import src.domain.entities.scheduled_reminder as scheduled_reminder_entity
import src.domain.official_reminder_templates as official_reminder_templates
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.reminder_service_port as reminder_service_port
import src.ports.scheduled_reminder_repository_port as scheduled_reminder_repository_port
import src.ports.task_scheduler_port as task_scheduler_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.scheduled_reminder_dto as scheduled_reminder_dto
import src.services.exceptions as service_exceptions
import src.services.reminder_date_formatter as reminder_date_formatter

logger = app_logs.get_logger(__name__)

# Business rule: reminders are sent at noon local time in Bogota, and never on
# Sundays. When the naive shifted datetime falls on a Sunday, we move it back
# one day so the message lands on Saturday instead.
_REMINDER_TIMEZONE = zoneinfo.ZoneInfo("America/Bogota")
_REMINDER_HOUR_LOCAL = 12
_SUNDAY_WEEKDAY = 6


class ReminderService(reminder_service_port.ReminderServicePort):
    def __init__(
        self,
        scheduled_reminder_repository: (
            scheduled_reminder_repository_port.ScheduledReminderRepositoryPort
        ),
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        whatsapp_connection_repository: (
            whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort
        ),
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort,
        task_scheduler: task_scheduler_port.TaskSchedulerPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._scheduled_reminder_repository = scheduled_reminder_repository
        self._agent_profile_repository = agent_profile_repository
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._whatsapp_provider = whatsapp_provider
        self._task_scheduler = task_scheduler
        self._id_generator = id_generator
        self._clock = clock

    def maybe_schedule_reminder(
        self,
        tenant_id: str,
        source_type: typing.Literal["SCHEDULING_REQUEST", "MANUAL_APPOINTMENT"],
        source_id: str,
        patient_whatsapp_user_id: str,
        patient_name: str,
        appointment_start_at: datetime.datetime,
        payment_status: typing.Literal["PAID", "PENDING"],
        appointment_modality: typing.Literal["VIRTUAL", "PRESENCIAL"] | None = None,
    ) -> None:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None or not agent_profile.appointment_reminder_enabled:
            return
        days_before = agent_profile.appointment_reminder_days_before
        if days_before is None:
            return

        # Select template based on payment_status.
        if payment_status == "PAID":
            template_name = agent_profile.appointment_reminder_attendance_template_name
        else:
            template_name = agent_profile.appointment_reminder_payment_template_name

        if template_name is None:
            logger.info(
                "reminder.skipped_no_template",
                extra={
                    "source_type": source_type,
                    "source_id": source_id,
                    "payment_status": payment_status,
                },
            )
            return

        template_language = "es"
        now_value = self._clock.now()
        reminder_datetime = _compute_reminder_datetime(appointment_start_at, days_before)
        delay_seconds = int((reminder_datetime - now_value).total_seconds())

        if delay_seconds <= 0:
            logger.info(
                "reminder.skipped_too_close",
                extra={
                    "source_type": source_type,
                    "source_id": source_id,
                    "days_before": days_before,
                },
            )
            return

        reminder_id = self._id_generator.new_id()
        reminder = scheduled_reminder_entity.ScheduledReminder(
            id=reminder_id,
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            patient_whatsapp_user_id=patient_whatsapp_user_id,
            patient_name=patient_name,
            appointment_start_at=appointment_start_at,
            reminder_scheduled_for=reminder_datetime,
            template_name=template_name,
            template_language=template_language,
            appointment_modality=appointment_modality,
            status="PENDING",
            created_at=now_value,
            updated_at=now_value,
        )

        try:
            task_name = self._task_scheduler.schedule_appointment_reminder(
                tenant_id=tenant_id,
                reminder_id=reminder_id,
                delay_seconds=delay_seconds,
            )
            reminder.cloud_task_name = task_name
        except service_exceptions.ExternalProviderError:
            logger.warning(
                "reminder.task_enqueue_failed",
                extra={"reminder_id": reminder_id, "source_id": source_id},
                exc_info=True,
            )
            return

        self._scheduled_reminder_repository.save(reminder)
        logger.info(
            "reminder.scheduled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="reminder.scheduled",
                    message="appointment reminder scheduled",
                    data={
                        "reminder_id": reminder_id,
                        "source_type": source_type,
                        "source_id": source_id,
                        "delay_seconds": delay_seconds,
                        "template_name": template_name,
                    },
                )
            },
        )

    def execute_reminder(self, tenant_id: str, reminder_id: str) -> dict[str, str]:
        reminder = self._scheduled_reminder_repository.get_by_id(tenant_id, reminder_id)
        if reminder is None:
            raise service_exceptions.EntityNotFoundError("scheduled reminder not found")

        if reminder.status != "PENDING":
            logger.info(
                "reminder.execute_skipped",
                extra={"reminder_id": reminder_id, "status": reminder.status},
            )
            return {"status": "skipped", "reason": f"status_is_{reminder.status.lower()}"}

        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None or not agent_profile.appointment_reminder_enabled:
            self._mark_reminder_cancelled(reminder, "reminder_disabled_at_execution_time")
            return {"status": "skipped", "reason": "reminder_disabled"}

        connection = self._whatsapp_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None or connection.status != "CONNECTED":
            self._mark_reminder_failed(reminder, "whatsapp_not_connected")
            raise service_exceptions.InvalidStateError("whatsapp not connected")
        if connection.access_token is None or connection.phone_number_id is None:
            self._mark_reminder_failed(reminder, "whatsapp_missing_credentials")
            raise service_exceptions.InvalidStateError("whatsapp missing credentials")

        now_value = self._clock.now()
        natural_date = reminder_date_formatter.format_natural_date(
            reminder.appointment_start_at,
            now_value,
        )
        template_kind = official_reminder_templates.by_name(reminder.template_name)

        if template_kind == "ATTENDANCE":
            modality_text = _format_modality_text(reminder.appointment_modality)
            body_parameters = [reminder.patient_name, natural_date, modality_text]
        elif template_kind == "PAYMENT":
            payment_details = (
                (agent_profile.payment_details_text or "").strip()
                if agent_profile.payment_details_text is not None
                else ""
            )
            if not payment_details:
                self._mark_reminder_failed(reminder, "payment_details_not_configured")
                logger.warning(
                    "reminder.payment_details_missing",
                    extra={"reminder_id": reminder_id, "tenant_id": tenant_id},
                )
                return {"status": "skipped", "reason": "payment_details_missing"}
            body_parameters = [reminder.patient_name, natural_date, payment_details]
        else:
            # Legacy or custom template: fall back to the previous 2-parameter shape
            # so pre-migration reminders don't explode.
            legacy_date = reminder.appointment_start_at.strftime("%d/%m/%Y %H:%M")
            body_parameters = [reminder.patient_name, legacy_date]

        try:
            message_id = self._whatsapp_provider.send_template_message(
                access_token=connection.access_token,
                phone_number_id=connection.phone_number_id,
                whatsapp_user_id=reminder.patient_whatsapp_user_id,
                template_name=reminder.template_name,
                language_code=reminder.template_language,
                body_parameters=body_parameters,
            )
        except service_exceptions.ExternalProviderError as exc:
            self._mark_reminder_failed(reminder, str(exc))
            raise

        reminder.status = "SENT"
        reminder.sent_at = now_value
        reminder.updated_at = now_value
        self._scheduled_reminder_repository.save(reminder)
        logger.info(
            "reminder.sent",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="reminder.sent",
                    message="appointment reminder sent",
                    data={
                        "reminder_id": reminder_id,
                        "message_id": message_id,
                        "template_name": reminder.template_name,
                    },
                )
            },
        )
        return {"status": "sent", "message_id": message_id}

    def cancel_reminders_for_source(
        self,
        tenant_id: str,
        source_type: typing.Literal["SCHEDULING_REQUEST", "MANUAL_APPOINTMENT"],
        source_id: str,
    ) -> None:
        pending_reminders = self._scheduled_reminder_repository.list_pending_by_source(
            tenant_id, source_type, source_id
        )
        for reminder in pending_reminders:
            if reminder.cloud_task_name is not None:
                try:
                    self._task_scheduler.cancel_task(reminder.cloud_task_name)
                except service_exceptions.ExternalProviderError:
                    logger.warning(
                        "reminder.cloud_task_cancel_failed",
                        extra={
                            "reminder_id": reminder.id,
                            "cloud_task_name": reminder.cloud_task_name,
                        },
                        exc_info=True,
                    )
            self._mark_reminder_cancelled(reminder, "source_cancelled_or_rescheduled")

        if pending_reminders:
            logger.info(
                "reminder.cancelled_for_source",
                extra={
                    "source_type": source_type,
                    "source_id": source_id,
                    "cancelled_count": len(pending_reminders),
                },
            )

    def cancel_reminders_by_template(self, tenant_id: str, template_name: str) -> None:
        pending_reminders = self._scheduled_reminder_repository.list_pending_by_template(
            tenant_id, template_name
        )
        for reminder in pending_reminders:
            if reminder.cloud_task_name is not None:
                try:
                    self._task_scheduler.cancel_task(reminder.cloud_task_name)
                except service_exceptions.ExternalProviderError:
                    logger.warning(
                        "reminder.cloud_task_cancel_failed",
                        extra={
                            "reminder_id": reminder.id,
                            "cloud_task_name": reminder.cloud_task_name,
                        },
                        exc_info=True,
                    )
            self._mark_reminder_cancelled(reminder, "template_deactivated")

        if pending_reminders:
            logger.info(
                "reminder.cancelled_by_template",
                extra={
                    "template_name": template_name,
                    "cancelled_count": len(pending_reminders),
                },
            )

    def swap_template_for_source(
        self,
        tenant_id: str,
        source_type: typing.Literal["SCHEDULING_REQUEST", "MANUAL_APPOINTMENT"],
        source_id: str,
        new_kind: official_reminder_templates.OfficialReminderKind,
    ) -> None:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            logger.info(
                "reminder.swap_skipped_no_profile",
                extra={"tenant_id": tenant_id, "source_id": source_id},
            )
            return

        if new_kind == "ATTENDANCE":
            new_template_name = agent_profile.appointment_reminder_attendance_template_name
        else:
            new_template_name = agent_profile.appointment_reminder_payment_template_name

        if new_template_name is None:
            logger.info(
                "reminder.swap_skipped_no_template",
                extra={"tenant_id": tenant_id, "source_id": source_id, "new_kind": new_kind},
            )
            return

        pending_reminders = self._scheduled_reminder_repository.list_pending_by_source(
            tenant_id, source_type, source_id
        )

        # Preserve reminder_scheduled_for and appointment_start_at from the first pending reminder.
        reminder_scheduled_for: datetime.datetime | None = None
        appointment_start_at: datetime.datetime | None = None
        patient_whatsapp_user_id: str | None = None
        patient_name: str | None = None
        appointment_modality: typing.Literal["VIRTUAL", "PRESENCIAL"] | None = None

        for reminder in pending_reminders:
            reminder_scheduled_for = reminder.reminder_scheduled_for
            appointment_start_at = reminder.appointment_start_at
            patient_whatsapp_user_id = reminder.patient_whatsapp_user_id
            patient_name = reminder.patient_name
            appointment_modality = reminder.appointment_modality
            # Cancel each pending reminder.
            if reminder.cloud_task_name is not None:
                try:
                    self._task_scheduler.cancel_task(reminder.cloud_task_name)
                except service_exceptions.ExternalProviderError:
                    logger.warning(
                        "reminder.cloud_task_cancel_failed",
                        extra={
                            "reminder_id": reminder.id,
                            "cloud_task_name": reminder.cloud_task_name,
                        },
                        exc_info=True,
                    )
            self._mark_reminder_cancelled(reminder, "payment_status_changed")

        if reminder_scheduled_for is None or appointment_start_at is None:
            logger.info(
                "reminder.swap_skipped_no_pending",
                extra={"tenant_id": tenant_id, "source_id": source_id},
            )
            return

        logger.info(
            "reminder.swap_triggered",
            extra={
                "source_type": source_type,
                "source_id": source_id,
                "new_kind": new_kind,
                "cancelled_count": len(pending_reminders),
            },
        )

        # Enqueue a new reminder with the new template preserving reminder_scheduled_for.
        now_value = self._clock.now()
        delay_seconds = int((reminder_scheduled_for - now_value).total_seconds())
        if delay_seconds <= 0:
            logger.info(
                "reminder.swap_skipped_too_close",
                extra={"tenant_id": tenant_id, "source_id": source_id},
            )
            return

        new_reminder_id = self._id_generator.new_id()
        new_reminder = scheduled_reminder_entity.ScheduledReminder(
            id=new_reminder_id,
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            patient_whatsapp_user_id=patient_whatsapp_user_id or "",
            patient_name=patient_name or "Paciente",
            appointment_start_at=appointment_start_at,
            reminder_scheduled_for=reminder_scheduled_for,
            template_name=new_template_name,
            template_language="es",
            appointment_modality=appointment_modality,
            status="PENDING",
            created_at=now_value,
            updated_at=now_value,
        )

        try:
            task_name = self._task_scheduler.schedule_appointment_reminder(
                tenant_id=tenant_id,
                reminder_id=new_reminder_id,
                delay_seconds=delay_seconds,
            )
            new_reminder.cloud_task_name = task_name
        except service_exceptions.ExternalProviderError:
            logger.warning(
                "reminder.swap_task_enqueue_failed",
                extra={"new_reminder_id": new_reminder_id, "source_id": source_id},
                exc_info=True,
            )
            return

        self._scheduled_reminder_repository.save(new_reminder)
        logger.info(
            "reminder.scheduled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="reminder.scheduled",
                    message="appointment reminder scheduled (swap)",
                    data={
                        "reminder_id": new_reminder_id,
                        "source_type": source_type,
                        "source_id": source_id,
                        "delay_seconds": delay_seconds,
                        "template_name": new_template_name,
                    },
                )
            },
        )

    def list_reminders(
        self, tenant_id: str, status: str | None = None
    ) -> scheduled_reminder_dto.ScheduledReminderListResponseDTO:
        reminders = self._scheduled_reminder_repository.list_by_tenant(tenant_id, status)
        sorted_reminders = sorted(reminders, key=lambda item: item.created_at, reverse=True)
        return scheduled_reminder_dto.ScheduledReminderListResponseDTO(
            items=[self._to_dto(item) for item in sorted_reminders]
        )

    def _mark_reminder_failed(
        self, reminder: scheduled_reminder_entity.ScheduledReminder, reason: str
    ) -> None:
        now_value = self._clock.now()
        reminder.status = "FAILED"
        reminder.failure_reason = reason
        reminder.updated_at = now_value
        self._scheduled_reminder_repository.save(reminder)

    def _mark_reminder_cancelled(
        self, reminder: scheduled_reminder_entity.ScheduledReminder, reason: str
    ) -> None:
        now_value = self._clock.now()
        reminder.status = "CANCELLED"
        reminder.failure_reason = reason
        reminder.updated_at = now_value
        self._scheduled_reminder_repository.save(reminder)

    def _to_dto(
        self, reminder: scheduled_reminder_entity.ScheduledReminder
    ) -> scheduled_reminder_dto.ScheduledReminderDTO:
        return scheduled_reminder_dto.ScheduledReminderDTO(
            reminder_id=reminder.id,
            source_type=reminder.source_type,
            source_id=reminder.source_id,
            patient_whatsapp_user_id=reminder.patient_whatsapp_user_id,
            patient_name=reminder.patient_name,
            appointment_start_at=reminder.appointment_start_at,
            reminder_scheduled_for=reminder.reminder_scheduled_for,
            template_name=reminder.template_name,
            status=reminder.status,
            created_at=reminder.created_at,
        )


def _format_modality_text(
    modality: typing.Literal["VIRTUAL", "PRESENCIAL"] | None,
) -> str:
    """Render the modality placeholder for the ATTENDANCE template.

    Defaults to ``"presencial"`` when the modality is unknown, which is the
    safer fallback: we avoid promising a Meet link that may not exist.
    """
    if modality == "VIRTUAL":
        return "virtual por Google Meet"
    return "presencial"


def _compute_reminder_datetime(
    appointment_start_at: datetime.datetime,
    days_before: int,
) -> datetime.datetime:
    """Compute the moment to send the reminder.

    Rules:
    - Send ``days_before`` days before the appointment.
    - Force the local (America/Bogota) time to 12:00 so reminders never go out
      at odd hours regardless of when the appointment itself is.
    - Never land on a Sunday: if the computed date is Sunday, move it one day
      earlier so it lands on Saturday instead.
    """
    shifted = appointment_start_at - datetime.timedelta(days=days_before)
    local_datetime = shifted.astimezone(_REMINDER_TIMEZONE).replace(
        hour=_REMINDER_HOUR_LOCAL,
        minute=0,
        second=0,
        microsecond=0,
    )
    if local_datetime.weekday() == _SUNDAY_WEEKDAY:
        local_datetime = local_datetime - datetime.timedelta(days=1)
    return local_datetime
