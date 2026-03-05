import abc

import src.domain.entities.scheduling_request as scheduling_request_entity


class SchedulingRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save_request(self, request: scheduling_request_entity.SchedulingRequest) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_request_by_id(
        self, tenant_id: str, request_id: str
    ) -> scheduling_request_entity.SchedulingRequest | None:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_request(self, tenant_id: str, request_id: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_requests_by_tenant(
        self, tenant_id: str, status: str | None = None
    ) -> list[scheduling_request_entity.SchedulingRequest]:
        raise NotImplementedError

    @abc.abstractmethod
    def list_requests_by_conversation(
        self, tenant_id: str, conversation_id: str
    ) -> list[scheduling_request_entity.SchedulingRequest]:
        raise NotImplementedError
