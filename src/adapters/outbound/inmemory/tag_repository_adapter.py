import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.tag as tag_entity
import src.ports.tag_repository_port as tag_repository_port


class InMemoryTagRepositoryAdapter(tag_repository_port.TagRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, tag: tag_entity.Tag) -> None:
        with self._store.lock:
            tag_key = (tag.tenant_id, tag.id)
            self._store.tag_by_tenant_and_id[tag_key] = tag.model_copy(deep=True)
            self._store.flush()

    def get_by_id(self, tenant_id: str, tag_id: str) -> tag_entity.Tag | None:
        with self._store.lock:
            tag_key = (tenant_id, tag_id)
            tag = self._store.tag_by_tenant_and_id.get(tag_key)
            if tag is None:
                return None
            return tag.model_copy(deep=True)

    def get_by_slug(self, tenant_id: str, slug: str) -> tag_entity.Tag | None:
        with self._store.lock:
            for (current_tenant_id, _), tag in self._store.tag_by_tenant_and_id.items():
                if current_tenant_id != tenant_id:
                    continue
                if tag.slug == slug:
                    return tag.model_copy(deep=True)
            return None

    def list_by_tenant(self, tenant_id: str) -> list[tag_entity.Tag]:
        with self._store.lock:
            items: list[tag_entity.Tag] = []
            for (current_tenant_id, _), tag in self._store.tag_by_tenant_and_id.items():
                if current_tenant_id != tenant_id:
                    continue
                items.append(tag.model_copy(deep=True))
            return items

    def delete(self, tenant_id: str, tag_id: str) -> None:
        with self._store.lock:
            tag_key = (tenant_id, tag_id)
            self._store.tag_by_tenant_and_id.pop(tag_key, None)
            self._store.flush()
