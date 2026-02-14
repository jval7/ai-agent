import abc


class MemoryAdminPort(abc.ABC):
    @abc.abstractmethod
    def reset_state(self) -> None:
        raise NotImplementedError
