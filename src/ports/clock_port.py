import abc
import datetime


class ClockPort(abc.ABC):
    @abc.abstractmethod
    def now(self) -> datetime.datetime:
        raise NotImplementedError

    @abc.abstractmethod
    def now_epoch_seconds(self) -> int:
        raise NotImplementedError
