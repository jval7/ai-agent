import src.domain.entities.tenant as tenant_entity
import src.ports.clock_port as clock_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.services.dto.tenant_dto as tenant_dto
import src.services.exceptions as service_exceptions


class TenantProfileService:
    def __init__(
        self,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._tenant_repository = tenant_repository
        self._clock = clock

    def get_profile(self, tenant_id: str) -> tenant_dto.TenantProfileDTO:
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise service_exceptions.EntityNotFoundError("tenant not found")
        return self._to_dto(tenant)

    def update_profile(
        self, tenant_id: str, dto: tenant_dto.UpdateTenantProfileDTO
    ) -> tenant_dto.TenantProfileDTO:
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise service_exceptions.EntityNotFoundError("tenant not found")

        updated_tenant = tenant_entity.Tenant(
            id=tenant.id,
            name=tenant.name,
            created_at=tenant.created_at,
            updated_at=self._clock.now(),
            professional_name=dto.professional_name,
        )
        self._tenant_repository.save(updated_tenant)
        return self._to_dto(updated_tenant)

    def _to_dto(self, tenant: tenant_entity.Tenant) -> tenant_dto.TenantProfileDTO:
        return tenant_dto.TenantProfileDTO(
            tenant_id=tenant.id,
            name=tenant.name,
            professional_name=tenant.professional_name,
        )
