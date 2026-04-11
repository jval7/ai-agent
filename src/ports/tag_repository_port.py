import abc

import src.domain.entities.tag as tag_entity


class TagRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, tag: tag_entity.Tag) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, tenant_id: str, tag_id: str) -> tag_entity.Tag | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_slug(self, tenant_id: str, slug: str) -> tag_entity.Tag | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_tenant(self, tenant_id: str) -> list[tag_entity.Tag]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, tenant_id: str, tag_id: str) -> None:
        raise NotImplementedError
