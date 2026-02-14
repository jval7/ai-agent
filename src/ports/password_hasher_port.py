import abc


class PasswordHasherPort(abc.ABC):
    @abc.abstractmethod
    def hash_password(self, raw_password: str) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def verify_password(self, raw_password: str, password_hash: str) -> bool:
        raise NotImplementedError
