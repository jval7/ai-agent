import abc

import src.domain.entities.tenant as tenant_entity


class TenantRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, tenant: tenant_entity.Tenant) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, tenant_id: str) -> tenant_entity.Tenant | None:
        raise NotImplementedError
