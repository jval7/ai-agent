import datetime
import threading

import src.domain.entities.invitation_token as invitation_token_entity
import src.ports.invitation_token_repository_port as invitation_token_repository_port


class InMemoryInvitationTokenRepositoryAdapter(
    invitation_token_repository_port.InvitationTokenRepositoryPort
):
    def __init__(self) -> None:
        self._records_by_hash: dict[str, invitation_token_entity.InvitationToken] = {}
        self._lock = threading.RLock()

    def save(self, token: invitation_token_entity.InvitationToken) -> None:
        with self._lock:
            self._records_by_hash[token.token_hash] = token.model_copy(deep=True)

    def get_by_hash(self, token_hash: str) -> invitation_token_entity.InvitationToken | None:
        with self._lock:
            token = self._records_by_hash.get(token_hash)
            if token is None:
                return None
            return token.model_copy(deep=True)

    def consume(
        self,
        token_hash: str,
        consumed_at: datetime.datetime,
    ) -> invitation_token_entity.InvitationToken | None:
        with self._lock:
            token = self._records_by_hash.get(token_hash)
            if token is None:
                return None
            if token.consumed_at is not None:
                return None
            if token.expires_at <= consumed_at:
                return None

            updated_token = token.model_copy(deep=True)
            updated_token.consumed_at = consumed_at
            self._records_by_hash[token_hash] = updated_token
            return updated_token.model_copy(deep=True)

    def invalidate_active_for_user(
        self,
        user_id: str,
        purpose: invitation_token_entity.InvitationPurpose,
        now: datetime.datetime,
    ) -> None:
        with self._lock:
            for token_hash, token in self._records_by_hash.items():
                if (
                    token.user_id == user_id
                    and token.purpose == purpose
                    and token.consumed_at is None
                ):
                    updated_token = token.model_copy(deep=True)
                    updated_token.consumed_at = now
                    self._records_by_hash[token_hash] = updated_token
