import datetime

import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.password_hasher_port as password_hasher_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.user_repository_port as user_repository_port
import src.services.constants as service_constants
import src.services.dto.user_admin_dto as user_admin_dto
import src.services.exceptions as service_exceptions


class UserAdminService:
    def __init__(
        self,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        user_repository: user_repository_port.UserRepositoryPort,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        password_hasher: password_hasher_port.PasswordHasherPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        default_system_prompt: str,
    ) -> None:
        self._tenant_repository = tenant_repository
        self._user_repository = user_repository
        self._agent_profile_repository = agent_profile_repository
        self._password_hasher = password_hasher
        self._id_generator = id_generator
        self._clock = clock
        self._default_system_prompt = default_system_prompt

    def create_professional(self, request: user_admin_dto.CreateProfessionalDTO) -> None:
        existing_user = self._user_repository.get_by_email(request.email)
        if existing_user is not None:
            raise service_exceptions.InvalidStateError("email is already registered")

        now_value = self._clock.now()
        tenant_id = self._id_generator.new_id()
        user_id = self._id_generator.new_id()

        tenant = tenant_entity.Tenant(
            id=tenant_id,
            name=request.tenant_name,
            created_at=now_value,
            updated_at=now_value,
        )
        self._tenant_repository.save(tenant)

        password_hash = self._password_hasher.hash_password(request.password)
        user = user_entity.User(
            id=user_id,
            tenant_id=tenant_id,
            email=request.email,
            password_hash=password_hash,
            role=service_constants.DEFAULT_PROFESSIONAL_ROLE,
            is_active=True,
            created_at=now_value,
        )
        self._user_repository.save(user)
        self._ensure_agent_profile(tenant_id=tenant_id, now_value=now_value)

    def reset_password(self, request: user_admin_dto.ResetPasswordDTO) -> None:
        user = self._user_repository.get_by_email(request.email)
        if user is None:
            raise service_exceptions.EntityNotFoundError("user not found")
        updated_user = user.model_copy(deep=True)
        updated_user.password_hash = self._password_hasher.hash_password(request.new_password)
        self._user_repository.save(updated_user)

    def delete_professional(self, request: user_admin_dto.DeleteProfessionalDTO) -> None:
        user = self._user_repository.get_by_email(request.email)
        if user is None:
            raise service_exceptions.EntityNotFoundError("user not found")
        tenant = self._tenant_repository.get_by_id(user.tenant_id)
        if tenant is None:
            raise service_exceptions.EntityNotFoundError("tenant not found")
        deleted = self._tenant_repository.delete_with_data(user.tenant_id)
        if not deleted:
            raise service_exceptions.EntityNotFoundError("tenant not found")

    def _ensure_agent_profile(self, tenant_id: str, now_value: datetime.datetime) -> None:
        existing_agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if existing_agent_profile is not None:
            return
        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt=self._default_system_prompt,
            updated_at=now_value,
        )
        self._agent_profile_repository.save(agent_profile)
