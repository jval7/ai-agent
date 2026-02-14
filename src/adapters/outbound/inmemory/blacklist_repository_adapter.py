import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.ports.blacklist_repository_port as blacklist_repository_port


class InMemoryBlacklistRepositoryAdapter(blacklist_repository_port.BlacklistRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, entry: blacklist_entry_entity.BlacklistEntry) -> None:
        with self._store.lock:
            blacklist_key = (entry.tenant_id, entry.whatsapp_user_id)
            self._store.blacklist_by_tenant_and_wa_user[blacklist_key] = entry.model_copy(deep=True)
            self._store.flush()

    def delete(self, tenant_id: str, whatsapp_user_id: str) -> None:
        with self._store.lock:
            blacklist_key = (tenant_id, whatsapp_user_id)
            if blacklist_key in self._store.blacklist_by_tenant_and_wa_user:
                self._store.blacklist_by_tenant_and_wa_user.pop(blacklist_key)
                self._store.flush()

    def exists(self, tenant_id: str, whatsapp_user_id: str) -> bool:
        with self._store.lock:
            blacklist_key = (tenant_id, whatsapp_user_id)
            return blacklist_key in self._store.blacklist_by_tenant_and_wa_user

    def list_by_tenant(self, tenant_id: str) -> list[blacklist_entry_entity.BlacklistEntry]:
        with self._store.lock:
            items: list[blacklist_entry_entity.BlacklistEntry] = []
            for (
                current_tenant_id,
                _,
            ), entry in self._store.blacklist_by_tenant_and_wa_user.items():
                if current_tenant_id != tenant_id:
                    continue
                items.append(entry.model_copy(deep=True))
            return items
