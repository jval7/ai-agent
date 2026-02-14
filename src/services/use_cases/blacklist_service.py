import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.ports.blacklist_repository_port as blacklist_repository_port
import src.ports.clock_port as clock_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.blacklist_dto as blacklist_dto
import src.services.exceptions as service_exceptions


class BlacklistService:
    def __init__(
        self,
        blacklist_repository: blacklist_repository_port.BlacklistRepositoryPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._blacklist_repository = blacklist_repository
        self._clock = clock

    def list_entries(
        self, claims: auth_dto.TokenClaimsDTO
    ) -> blacklist_dto.BlacklistListResponseDTO:
        self._ensure_owner(claims)
        entries = self._blacklist_repository.list_by_tenant(claims.tenant_id)
        sorted_entries = sorted(entries, key=lambda item: item.created_at)

        items: list[blacklist_dto.BlacklistEntryDTO] = []
        for entry in sorted_entries:
            items.append(
                blacklist_dto.BlacklistEntryDTO(
                    tenant_id=entry.tenant_id,
                    whatsapp_user_id=entry.whatsapp_user_id,
                    created_at=entry.created_at,
                )
            )

        return blacklist_dto.BlacklistListResponseDTO(items=items)

    def upsert_entry(
        self,
        claims: auth_dto.TokenClaimsDTO,
        upsert_dto: blacklist_dto.UpsertBlacklistEntryDTO,
    ) -> blacklist_dto.BlacklistEntryDTO:
        self._ensure_owner(claims)
        existing_entries = self._blacklist_repository.list_by_tenant(claims.tenant_id)
        for existing_entry in existing_entries:
            if existing_entry.whatsapp_user_id == upsert_dto.whatsapp_user_id:
                return blacklist_dto.BlacklistEntryDTO(
                    tenant_id=existing_entry.tenant_id,
                    whatsapp_user_id=existing_entry.whatsapp_user_id,
                    created_at=existing_entry.created_at,
                )

        entry = blacklist_entry_entity.BlacklistEntry(
            tenant_id=claims.tenant_id,
            whatsapp_user_id=upsert_dto.whatsapp_user_id,
            created_at=self._clock.now(),
        )
        self._blacklist_repository.save(entry)
        return blacklist_dto.BlacklistEntryDTO(
            tenant_id=entry.tenant_id,
            whatsapp_user_id=entry.whatsapp_user_id,
            created_at=entry.created_at,
        )

    def delete_entry(self, claims: auth_dto.TokenClaimsDTO, whatsapp_user_id: str) -> None:
        self._ensure_owner(claims)
        self._blacklist_repository.delete(claims.tenant_id, whatsapp_user_id)

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")
