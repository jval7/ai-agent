import datetime

import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.processed_webhook_event as processed_webhook_event_entity
import src.ports.processed_webhook_event_repository_port as processed_webhook_event_repository_port


class InMemoryProcessedWebhookEventRepositoryAdapter(
    processed_webhook_event_repository_port.ProcessedWebhookEventRepositoryPort
):
    _claim_timeout_seconds = 120

    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store
        self._status_by_key: dict[tuple[str, str], str] = {}
        self._claimed_at_by_key: dict[tuple[str, str], datetime.datetime] = {}

    def claim_for_processing(
        self,
        tenant_id: str,
        provider_event_id: str,
        claimed_at: datetime.datetime,
    ) -> bool:
        with self._store.lock:
            key = (tenant_id, provider_event_id)
            existing_status = self._status_by_key.get(key)
            should_claim = key not in self._store.processed_events
            if not should_claim and existing_status == "FAILED":
                should_claim = True
            if not should_claim and existing_status == "CLAIMED":
                existing_claimed_at = self._claimed_at_by_key.get(key)
                if existing_claimed_at is not None:
                    claim_expiration = existing_claimed_at + datetime.timedelta(
                        seconds=self._claim_timeout_seconds
                    )
                    should_claim = claim_expiration <= claimed_at

            if not should_claim:
                return False

            self._store.processed_events.add(key)
            self._status_by_key[key] = "CLAIMED"
            self._claimed_at_by_key[key] = claimed_at
            self._store.flush()
            return True

    def mark_processed(
        self,
        tenant_id: str,
        provider_event_id: str,
        processed_at: datetime.datetime,
    ) -> None:
        del processed_at
        with self._store.lock:
            key = (tenant_id, provider_event_id)
            self._store.processed_events.add(key)
            self._status_by_key[key] = "PROCESSED"
            self._store.flush()

    def mark_failed(
        self,
        tenant_id: str,
        provider_event_id: str,
        failed_at: datetime.datetime,
        failure_reason: str,
    ) -> None:
        del failed_at
        del failure_reason
        with self._store.lock:
            key = (tenant_id, provider_event_id)
            self._store.processed_events.add(key)
            self._status_by_key[key] = "FAILED"
            self._store.flush()

    def exists(self, tenant_id: str, provider_event_id: str) -> bool:
        with self._store.lock:
            return (tenant_id, provider_event_id) in self._store.processed_events

    def save(self, event: processed_webhook_event_entity.ProcessedWebhookEvent) -> None:
        with self._store.lock:
            key = (event.tenant_id, event.provider_event_id)
            self._store.processed_events.add(key)
            self._store.flush()
