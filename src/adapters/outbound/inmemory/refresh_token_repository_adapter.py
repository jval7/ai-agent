import datetime
import threading

import src.domain.entities.refresh_token as refresh_token_entity
import src.ports.refresh_token_repository_port as refresh_token_repository_port


class InMemoryRefreshTokenRepositoryAdapter(
    refresh_token_repository_port.RefreshTokenRepositoryPort
):
    def __init__(self) -> None:
        self._records_by_jti: dict[str, refresh_token_entity.RefreshTokenRecord] = {}
        self._lock = threading.RLock()

    def create(self, record: refresh_token_entity.RefreshTokenRecord) -> None:
        with self._lock:
            self._records_by_jti[record.jti] = record.model_copy(deep=True)

    def get_by_jti(self, jti: str) -> refresh_token_entity.RefreshTokenRecord | None:
        with self._lock:
            record = self._records_by_jti.get(jti)
            if record is None:
                return None
            return record.model_copy(deep=True)

    def consume_for_rotation(
        self,
        jti: str,
        tenant_id: str,
        user_id: str,
        token_hash: str,
        revoked_at: datetime.datetime,
    ) -> refresh_token_entity.RefreshTokenRecord | None:
        with self._lock:
            record = self._records_by_jti.get(jti)
            if record is None:
                return None
            if record.tenant_id != tenant_id:
                return None
            if record.user_id != user_id:
                return None
            if record.token_hash != token_hash:
                return None
            if record.revoked_at is not None:
                return None

            updated_record = record.model_copy(deep=True)
            updated_record.revoked_at = revoked_at
            self._records_by_jti[jti] = updated_record
            return updated_record.model_copy(deep=True)

    def revoke(self, jti: str, revoked_at: datetime.datetime) -> bool:
        with self._lock:
            record = self._records_by_jti.get(jti)
            if record is None:
                return False
            updated_record = record.model_copy(deep=True)
            updated_record.revoked_at = revoked_at
            self._records_by_jti[jti] = updated_record
            return True
