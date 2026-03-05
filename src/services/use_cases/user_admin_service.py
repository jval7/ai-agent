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

    def bootstrap_master(self, request: user_admin_dto.BootstrapMasterDTO) -> None:
        existing_user = self._user_repository.get_by_email(request.master_email)
        if existing_user is not None:
            self._promote_existing_user_to_master(existing_user, request.master_password)
            return

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

        password_hash = self._password_hasher.hash_password(request.master_password)
        master_user = user_entity.User(
            id=user_id,
            tenant_id=tenant_id,
            email=request.master_email,
            password_hash=password_hash,
            role=service_constants.DEFAULT_OWNER_ROLE,
            is_active=True,
            is_master=True,
            created_at=now_value,
        )
        self._user_repository.save(master_user)
        self._ensure_agent_profile(tenant_id=tenant_id, now_value=now_value)

    def create_user(self, request: user_admin_dto.CreateUserByMasterDTO) -> None:
        master_user = self._authenticate_master(
            master_email=request.master_email,
            master_password=request.master_password,
        )
        existing_user = self._user_repository.get_by_email(request.email)
        if existing_user is not None:
            raise service_exceptions.InvalidStateError("email is already registered")

        now_value = self._clock.now()
        user = user_entity.User(
            id=self._id_generator.new_id(),
            tenant_id=master_user.tenant_id,
            email=request.email,
            password_hash=self._password_hasher.hash_password(request.password),
            role=service_constants.DEFAULT_OWNER_ROLE,
            is_active=True,
            is_master=False,
            created_at=now_value,
        )
        self._user_repository.save(user)

    def delete_user(self, request: user_admin_dto.DeleteUserByMasterDTO) -> None:
        master_user = self._authenticate_master(
            master_email=request.master_email,
            master_password=request.master_password,
        )
        target_user = self._user_repository.get_by_email(request.email)
        if target_user is None:
            raise service_exceptions.EntityNotFoundError("user not found")
        if target_user.id == master_user.id:
            raise service_exceptions.InvalidStateError("master user cannot delete itself")
        if target_user.is_master:
            raise service_exceptions.InvalidStateError("master user cannot be deleted")
        delete_ok = self._user_repository.delete_by_id(target_user.id)
        if not delete_ok:
            raise service_exceptions.EntityNotFoundError("user not found")

    def _promote_existing_user_to_master(
        self,
        existing_user: user_entity.User,
        master_password: str,
    ) -> None:
        if not existing_user.is_active:
            raise service_exceptions.AuthenticationError("master user is inactive")
        is_password_valid = self._password_hasher.verify_password(
            master_password,
            existing_user.password_hash,
        )
        if not is_password_valid:
            raise service_exceptions.AuthenticationError("invalid master credentials")

        updated_user = existing_user.model_copy(deep=True)
        updated_user.role = service_constants.DEFAULT_OWNER_ROLE
        updated_user.is_master = True
        self._user_repository.save(updated_user)
        self._ensure_agent_profile(existing_user.tenant_id, self._clock.now())

    def _authenticate_master(self, master_email: str, master_password: str) -> user_entity.User:
        master_user = self._user_repository.get_by_email(master_email)
        if master_user is None:
            raise service_exceptions.AuthenticationError("invalid master credentials")
        if not master_user.is_active:
            raise service_exceptions.AuthenticationError("master user is inactive")

        is_password_valid = self._password_hasher.verify_password(
            master_password,
            master_user.password_hash,
        )
        if not is_password_valid:
            raise service_exceptions.AuthenticationError("invalid master credentials")
        if not master_user.is_master:
            raise service_exceptions.AuthorizationError("master privileges required")
        return master_user

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
