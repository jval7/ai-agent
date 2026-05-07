import abc
import asyncio
import dataclasses
import typing


@dataclasses.dataclass(frozen=True)
class StreamEvent:
    type: str
    payload: dict[str, str]


@dataclasses.dataclass(frozen=True)
class EventSubscription:
    queue: asyncio.Queue[StreamEvent]
    teardown: typing.Callable[[], None]


class EventStreamPort(abc.ABC):
    @abc.abstractmethod
    def subscribe(self, tenant_id: str) -> EventSubscription:
        raise NotImplementedError
