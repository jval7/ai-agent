import abc

import src.domain.entities.scheduled_reminder as scheduled_reminder_entity


class ScheduledReminderRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, reminder: scheduled_reminder_entity.ScheduledReminder) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(
        self, tenant_id: str, reminder_id: str
    ) -> scheduled_reminder_entity.ScheduledReminder | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_tenant(
        self, tenant_id: str, status: str | None = None
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        raise NotImplementedError

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: str, status: str | None = None) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def list_pending_by_source(
        self, tenant_id: str, source_type: str, source_id: str
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        raise NotImplementedError

    @abc.abstractmethod
    def list_pending_by_template(
        self, tenant_id: str, template_name: str
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        raise NotImplementedError

    @abc.abstractmethod
    def find_by_provider_message_id(
        self, tenant_id: str, provider_message_id: str
    ) -> scheduled_reminder_entity.ScheduledReminder | None:
        raise NotImplementedError
