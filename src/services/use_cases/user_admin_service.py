import datetime
import secrets

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
import src.services.use_cases.invitation_service as invitation_service_mod


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
        invitation_service: invitation_service_mod.InvitationService | None = None,
    ) -> None:
        self._tenant_repository = tenant_repository
        self._user_repository = user_repository
        self._agent_profile_repository = agent_profile_repository
        self._password_hasher = password_hasher
        self._id_generator = id_generator
        self._clock = clock
        self._default_system_prompt = default_system_prompt
        self._invitation_service = invitation_service

    def create_professional(self, request: user_admin_dto.CreateProfessionalDTO) -> None:
        existing_user = self._user_repository.get_by_email(request.email)
        if existing_user is not None:
            raise service_exceptions.InvalidStateError("email is already registered")

        now_value = self._clock.now()

        if request.role == service_constants.ROLE_ADMIN:
            user_id = self._id_generator.new_id()
            tenant = self._get_or_create_admin_tenant(now_value=now_value)
        else:
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
            tenant_id=tenant.id,
            email=request.email,
            password_hash=password_hash,
            role=request.role,
            is_active=True,
            created_at=now_value,
        )
        self._user_repository.save(user)
        if request.role != service_constants.ROLE_ADMIN:
            self._ensure_agent_profile(tenant_id=tenant.id, now_value=now_value)

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
        if tenant.is_admin_tenant:
            raise service_exceptions.InvalidStateError(
                "cannot delete admin tenant singleton; remove the user record instead"
            )
        deleted = self._tenant_repository.delete_with_data(user.tenant_id)
        if not deleted:
            raise service_exceptions.EntityNotFoundError("tenant not found")

    def list_professionals(self) -> list[user_admin_dto.ProfessionalSummaryDTO]:
        users = self._user_repository.list_all()
        tenant_name_by_id: dict[str, str] = {}
        summaries: list[user_admin_dto.ProfessionalSummaryDTO] = []
        for user in users:
            tenant_name = tenant_name_by_id.get(user.tenant_id)
            if tenant_name is None:
                tenant = self._tenant_repository.get_by_id(user.tenant_id)
                tenant_name = tenant.name if tenant is not None else ""
                tenant_name_by_id[user.tenant_id] = tenant_name
            summaries.append(
                user_admin_dto.ProfessionalSummaryDTO(
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    tenant_name=tenant_name,
                    email=user.email,
                    role=user.role,
                    is_active=user.is_active,
                    created_at=user.created_at,
                )
            )
        summaries.sort(key=lambda summary: summary.email)
        return summaries

    def invite_professional(self, request: user_admin_dto.InviteProfessionalDTO) -> None:
        if self._invitation_service is None:
            raise service_exceptions.InvalidStateError(
                "invitation_service is required for invite_professional"
            )
        existing_user = self._user_repository.get_by_email(request.email)
        if existing_user is not None:
            raise service_exceptions.InvalidStateError("email is already registered")

        now_value = self._clock.now()

        if request.role == service_constants.ROLE_ADMIN:
            user_id = self._id_generator.new_id()
            tenant = self._get_or_create_admin_tenant(now_value=now_value)
        else:
            tenant_id = self._id_generator.new_id()
            user_id = self._id_generator.new_id()
            tenant = tenant_entity.Tenant(
                id=tenant_id,
                name=request.tenant_name,
                created_at=now_value,
                updated_at=now_value,
                professional_name=request.professional_name,
            )
            self._tenant_repository.save(tenant)

        placeholder_hash = self._password_hasher.hash_password(secrets.token_urlsafe(32))
        user = user_entity.User(
            id=user_id,
            tenant_id=tenant.id,
            email=request.email,
            password_hash=placeholder_hash,
            role=request.role,
            is_active=False,
            created_at=now_value,
        )
        self._user_repository.save(user)
        if request.role != service_constants.ROLE_ADMIN:
            self._ensure_agent_profile(tenant_id=tenant.id, now_value=now_value)

        self._invitation_service.issue_account_setup_invitation(user=user, tenant=tenant)

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

    def _get_or_create_admin_tenant(self, now_value: datetime.datetime) -> tenant_entity.Tenant:
        existing_admin_tenant = self._tenant_repository.get_admin_tenant()
        if existing_admin_tenant is not None:
            return existing_admin_tenant
        tenant_id = self._id_generator.new_id()
        admin_tenant = tenant_entity.Tenant(
            id=tenant_id,
            name=service_constants.ADMIN_TENANT_NAME,
            created_at=now_value,
            updated_at=now_value,
            is_admin_tenant=True,
        )
        self._tenant_repository.save(admin_tenant)
        return admin_tenant
