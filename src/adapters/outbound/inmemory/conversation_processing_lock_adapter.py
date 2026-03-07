import datetime

import src.adapters.outbound.inmemory.store as in_memory_store
import src.ports.conversation_processing_lock_port as conversation_processing_lock_port


class InMemoryConversationProcessingLockAdapter(
    conversation_processing_lock_port.ConversationProcessingLockPort
):
    _lock_timeout_seconds = 120

    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def try_acquire(
        self,
        tenant_id: str,
        conversation_id: str,
        holder_id: str,
        acquired_at: datetime.datetime,
    ) -> bool:
        with self._store.lock:
            key = (tenant_id, conversation_id)
            existing = self._store.conversation_processing_locks.get(key)

            if existing is None:
                self._store.conversation_processing_locks[key] = {
                    "holder_id": holder_id,
                    "status": "LOCKED",
                    "acquired_at": acquired_at,
                }
                return True

            if existing["status"] == "RELEASED":
                self._store.conversation_processing_locks[key] = {
                    "holder_id": holder_id,
                    "status": "LOCKED",
                    "acquired_at": acquired_at,
                }
                return True

            if existing["status"] == "LOCKED":
                existing_acquired_at = existing["acquired_at"]
                if isinstance(existing_acquired_at, datetime.datetime):
                    lock_expiration = existing_acquired_at + datetime.timedelta(
                        seconds=self._lock_timeout_seconds
                    )
                    if lock_expiration <= acquired_at:
                        self._store.conversation_processing_locks[key] = {
                            "holder_id": holder_id,
                            "status": "LOCKED",
                            "acquired_at": acquired_at,
                        }
                        return True

            return False

    def release(
        self,
        tenant_id: str,
        conversation_id: str,
        holder_id: str,
    ) -> None:
        with self._store.lock:
            key = (tenant_id, conversation_id)
            existing = self._store.conversation_processing_locks.get(key)
            if existing is not None and existing["holder_id"] == holder_id:
                existing["status"] = "RELEASED"
