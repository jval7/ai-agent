import abc

import src.domain.entities.blacklist_entry as blacklist_entry_entity


class BlacklistRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, entry: blacklist_entry_entity.BlacklistEntry) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, tenant_id: str, whatsapp_user_id: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, tenant_id: str, whatsapp_user_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_tenant(self, tenant_id: str) -> list[blacklist_entry_entity.BlacklistEntry]:
        raise NotImplementedError
