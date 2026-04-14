import datetime
import typing

import src.domain.entities.scheduled_reminder as scheduled_reminder_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.scheduled_reminder_repository_port as scheduled_reminder_repository_port
import src.ports.task_scheduler_port as task_scheduler_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.scheduled_reminder_dto as scheduled_reminder_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class ReminderService:
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
    ) -> None:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None or not agent_profile.appointment_reminder_enabled:
            return
        days_before = agent_profile.appointment_reminder_days_before
        template_name = agent_profile.appointment_reminder_template_name
        template_language = agent_profile.appointment_reminder_template_language
        if days_before is None or template_name is None:
            return

        now_value = self._clock.now()
        reminder_datetime = appointment_start_at - datetime.timedelta(days=days_before)
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

        appointment_date_str = reminder.appointment_start_at.strftime("%d/%m/%Y %H:%M")
        body_parameters = [reminder.patient_name, appointment_date_str]

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

        now_value = self._clock.now()
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
