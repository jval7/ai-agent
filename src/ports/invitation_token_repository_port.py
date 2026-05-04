import abc
import datetime

import src.domain.entities.invitation_token as invitation_token_entity


class InvitationTokenRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, token: invitation_token_entity.InvitationToken) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_hash(self, token_hash: str) -> invitation_token_entity.InvitationToken | None:
        raise NotImplementedError

    @abc.abstractmethod
    def consume(
        self,
        token_hash: str,
        consumed_at: datetime.datetime,
    ) -> invitation_token_entity.InvitationToken | None:
        raise NotImplementedError

    @abc.abstractmethod
    def invalidate_active_for_user(
        self,
        user_id: str,
        purpose: invitation_token_entity.InvitationPurpose,
        now: datetime.datetime,
    ) -> None:
        raise NotImplementedError
