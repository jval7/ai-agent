import abc


class MemoryAdminPort(abc.ABC):
    @abc.abstractmethod
    def reset_state(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def reset_chat_state(self) -> None:
        raise NotImplementedError
