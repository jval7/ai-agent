import abc
import datetime

import src.domain.entities.processed_webhook_event as processed_webhook_event_entity


class ProcessedWebhookEventRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def claim_for_processing(
        self,
        tenant_id: str,
        provider_event_id: str,
        claimed_at: datetime.datetime,
    ) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def mark_processed(
        self,
        tenant_id: str,
        provider_event_id: str,
        processed_at: datetime.datetime,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def mark_failed(
        self,
        tenant_id: str,
        provider_event_id: str,
        failed_at: datetime.datetime,
        failure_reason: str,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, tenant_id: str, provider_event_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, event: processed_webhook_event_entity.ProcessedWebhookEvent) -> None:
        raise NotImplementedError
