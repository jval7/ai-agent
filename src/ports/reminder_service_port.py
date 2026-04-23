import abc


class ReminderServicePort(abc.ABC):
    """Minimal port for reminder service operations needed by other services.

    This port exists to break the direct dependency between WhatsappTemplateService
    and the concrete ReminderService, respecting the hexagonal architecture boundary.
    """

    @abc.abstractmethod
    def cancel_reminders_by_template(self, tenant_id: str, template_name: str) -> None:
        raise NotImplementedError
