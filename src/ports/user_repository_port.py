import abc

import src.domain.entities.user as user_entity


class UserRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, user: user_entity.User) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_email(self, email: str) -> user_entity.User | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, user_id: str) -> user_entity.User | None:
        raise NotImplementedError
