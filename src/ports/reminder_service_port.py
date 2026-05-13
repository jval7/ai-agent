import abc

import src.services.dto.webhook_dto as webhook_dto


class ReminderServicePort(abc.ABC):
    """Minimal port for reminder service operations needed by other services.

    This port exists to break the direct dependency between WhatsappTemplateService
    and the concrete ReminderService, respecting the hexagonal architecture boundary.
    """

    @abc.abstractmethod
    def cancel_reminders_by_template(self, tenant_id: str, template_name: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def apply_message_status_event(
        self,
        tenant_id: str,
        event: webhook_dto.MessageStatusEventDTO,
    ) -> None:
        """Apply a Meta delivery callback to the matching reminder, if any.

        No-op when no reminder maps to ``event.provider_message_id``: this
        callback may correspond to a regular conversation message instead.
        """
        raise NotImplementedError
