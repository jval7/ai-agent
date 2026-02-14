import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.processed_webhook_event as processed_webhook_event_entity
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port


class InMemoryProcessedWebhookEventRepositoryAdapter(
    processed_webhook_event_repository_port.ProcessedWebhookEventRepositoryPort
):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def exists(self, tenant_id: str, provider_event_id: str) -> bool:
        with self._store.lock:
            return (tenant_id, provider_event_id) in self._store.processed_events

    def save(self, event: processed_webhook_event_entity.ProcessedWebhookEvent) -> None:
        with self._store.lock:
            key = (event.tenant_id, event.provider_event_id)
            self._store.processed_events.add(key)
            self._store.flush()
