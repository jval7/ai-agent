import src.domain.entities.scheduled_reminder as scheduled_reminder_entity
import src.ports.scheduled_reminder_repository_port as scheduled_reminder_repository_port


class InMemoryScheduledReminderRepositoryAdapter(
    scheduled_reminder_repository_port.ScheduledReminderRepositoryPort
):
    def __init__(self) -> None:
        self._reminders: list[scheduled_reminder_entity.ScheduledReminder] = []

    def save(self, reminder: scheduled_reminder_entity.ScheduledReminder) -> None:
        reminder_copy = scheduled_reminder_entity.ScheduledReminder.model_validate(
            reminder.model_dump()
        )
        for index, existing in enumerate(self._reminders):
            if existing.id == reminder.id and existing.tenant_id == reminder.tenant_id:
                self._reminders[index] = reminder_copy
                return
        self._reminders.append(reminder_copy)

    def get_by_id(
        self,
        tenant_id: str,
        reminder_id: str,
    ) -> scheduled_reminder_entity.ScheduledReminder | None:
        for reminder in self._reminders:
            if reminder.id == reminder_id and reminder.tenant_id == tenant_id:
                return scheduled_reminder_entity.ScheduledReminder.model_validate(
                    reminder.model_dump()
                )
        return None

    def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        result: list[scheduled_reminder_entity.ScheduledReminder] = []
        for reminder in self._reminders:
            if reminder.tenant_id != tenant_id:
                continue
            if status is not None and reminder.status != status:
                continue
            result.append(
                scheduled_reminder_entity.ScheduledReminder.model_validate(reminder.model_dump())
            )
        return result

    def count_by_tenant(self, tenant_id: str, status: str | None = None) -> int:
        count = 0
        for reminder in self._reminders:
            if reminder.tenant_id != tenant_id:
                continue
            if status is not None and reminder.status != status:
                continue
            count += 1
        return count

    def list_pending_by_source(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        result: list[scheduled_reminder_entity.ScheduledReminder] = []
        for reminder in self._reminders:
            if reminder.tenant_id != tenant_id:
                continue
            if reminder.source_type != source_type:
                continue
            if reminder.source_id != source_id:
                continue
            if reminder.status != "PENDING":
                continue
            result.append(
                scheduled_reminder_entity.ScheduledReminder.model_validate(reminder.model_dump())
            )
        return result

    def list_pending_by_template(
        self,
        tenant_id: str,
        template_name: str,
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        result: list[scheduled_reminder_entity.ScheduledReminder] = []
        for reminder in self._reminders:
            if reminder.tenant_id != tenant_id:
                continue
            if reminder.template_name != template_name:
                continue
            if reminder.status != "PENDING":
                continue
            result.append(
                scheduled_reminder_entity.ScheduledReminder.model_validate(reminder.model_dump())
            )
        return result

    def find_by_provider_message_id(
        self,
        tenant_id: str,
        provider_message_id: str,
    ) -> scheduled_reminder_entity.ScheduledReminder | None:
        for reminder in self._reminders:
            if reminder.tenant_id != tenant_id:
                continue
            if reminder.provider_message_id != provider_message_id:
                continue
            return scheduled_reminder_entity.ScheduledReminder.model_validate(reminder.model_dump())
        return None
