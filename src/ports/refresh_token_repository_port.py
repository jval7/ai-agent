import abc
import datetime

import src.domain.entities.refresh_token as refresh_token_entity


class RefreshTokenRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def create(self, record: refresh_token_entity.RefreshTokenRecord) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_jti(self, jti: str) -> refresh_token_entity.RefreshTokenRecord | None:
        raise NotImplementedError

    @abc.abstractmethod
    def consume_for_rotation(
        self,
        jti: str,
        tenant_id: str,
        user_id: str,
        token_hash: str,
        revoked_at: datetime.datetime,
    ) -> refresh_token_entity.RefreshTokenRecord | None:
        raise NotImplementedError

    @abc.abstractmethod
    def revoke(self, jti: str, revoked_at: datetime.datetime) -> bool:
        raise NotImplementedError
