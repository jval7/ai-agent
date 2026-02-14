import abc

import src.domain.entities.processed_webhook_event as processed_webhook_event_entity


class ProcessedWebhookEventRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def exists(self, tenant_id: str, provider_event_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, event: processed_webhook_event_entity.ProcessedWebhookEvent) -> None:
        raise NotImplementedError
