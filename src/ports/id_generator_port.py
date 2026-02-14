import abc


class IdGeneratorPort(abc.ABC):
    @abc.abstractmethod
    def new_id(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def new_token(self) -> str:
        raise NotImplementedError
