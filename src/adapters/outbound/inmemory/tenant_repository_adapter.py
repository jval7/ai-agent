import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.tenant as tenant_entity
import src.ports.tenant_repository_port as tenant_repository_port


class InMemoryTenantRepositoryAdapter(tenant_repository_port.TenantRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, tenant: tenant_entity.Tenant) -> None:
        with self._store.lock:
            self._store.tenants_by_id[tenant.id] = tenant.model_copy(deep=True)
            self._store.flush()

    def get_by_id(self, tenant_id: str) -> tenant_entity.Tenant | None:
        with self._store.lock:
            tenant = self._store.tenants_by_id.get(tenant_id)
            if tenant is None:
                return None
            return tenant.model_copy(deep=True)
