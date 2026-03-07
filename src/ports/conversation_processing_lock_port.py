import abc
import datetime


class ConversationProcessingLockPort(abc.ABC):
    @abc.abstractmethod
    def try_acquire(
        self,
        tenant_id: str,
        conversation_id: str,
        holder_id: str,
        acquired_at: datetime.datetime,
    ) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def release(
        self,
        tenant_id: str,
        conversation_id: str,
        holder_id: str,
    ) -> None:
        raise NotImplementedError
