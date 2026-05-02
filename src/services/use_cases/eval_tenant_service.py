import uuid

import src.adapters.outbound.firestore.errors as firestore_errors
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.password_hasher_port as password_hasher_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.user_repository_port as user_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.eval_tenant_dto as eval_tenant_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service_mod

logger = app_logs.get_logger(__name__)


class EvalTenantService:
    def __init__(
        self,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        user_repository: user_repository_port.UserRepositoryPort,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        whatsapp_connection_repository: whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort,
        password_hasher: password_hasher_port.PasswordHasherPort,
        auth_service: auth_service_mod.AuthService,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._tenant_repository = tenant_repository
        self._user_repository = user_repository
        self._agent_profile_repository = agent_profile_repository
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._password_hasher = password_hasher
        self._auth_service = auth_service
        self._id_generator = id_generator
        self._clock = clock

    def create_eval_tenant(
        self,
        run_id: str,
        shape_name: str,
    ) -> eval_tenant_dto.EvalTenantCreatedDTO:
        email = f"eval-{shape_name}-{run_id}@eval.local"
        password = uuid.uuid4().hex
        now = self._clock.now()

        tenant_id = self._id_generator.new_id()
        user_id = self._id_generator.new_id()
        phone_number_id = f"mock_eval_{run_id}_{shape_name}"

        tenant = tenant_entity.Tenant(
            id=tenant_id,
            name=f"eval-{shape_name}-{run_id}",
            created_at=now,
            updated_at=now,
            is_eval_tenant=True,
        )
        self._tenant_repository.save(tenant)

        password_hash = self._password_hasher.hash_password(password)
        user = user_entity.User(
            id=user_id,
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            role=service_constants.DEFAULT_PROFESSIONAL_ROLE,
            is_active=True,
            created_at=now,
        )
        self._user_repository.save(user)

        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt="",
            updated_at=now,
        )
        self._agent_profile_repository.save(agent_profile)

        wa_connection = whatsapp_connection_entity.WhatsappConnection(
            tenant_id=tenant_id,
            phone_number_id=phone_number_id,
            business_account_id=f"mock_baid_{run_id}",
            access_token="mock_token",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=now,
        )
        self._whatsapp_connection_repository.save(wa_connection)

        auth_tokens = self._auth_service.login(auth_dto.LoginDTO(email=email, password=password))

        logger.info(
            "eval_tenant.created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="eval_tenant.created",
                    message="eval tenant created",
                    data={
                        "tenant_id": tenant_id,
                        "run_id": run_id,
                        "shape_name": shape_name,
                        "phone_number_id": phone_number_id,
                    },
                )
            },
        )
        return eval_tenant_dto.EvalTenantCreatedDTO(
            tenant_id=tenant_id,
            email=email,
            password=password,
            phone_number_id=phone_number_id,
            access_token=auth_tokens.access_token,
            refresh_token=auth_tokens.refresh_token,
        )

    def delete_eval_tenant(self, tenant_id: str) -> None:
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise service_exceptions.EntityNotFoundError(f"eval tenant {tenant_id} not found")
        if not tenant.is_eval_tenant:
            raise service_exceptions.InvalidStateError(
                f"tenant {tenant_id} is not an eval tenant — refusing cascade delete"
            )

        # Cascade delete: tenant_repository handles WA phone index, user indexes,
        # and recursive delete of all subcollections (conversations, scheduling_requests,
        # patients, agent_profile, whatsapp_connection, etc.).
        try:
            self._tenant_repository.delete_with_data(tenant_id)
        except (
            service_exceptions.ServiceError,
            firestore_errors.FirestoreRepositoryError,
        ) as error:
            logger.warning(
                "eval_tenant.delete.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="eval_tenant.delete.failed",
                        message=str(error),
                        data={"tenant_id": tenant_id},
                    )
                },
            )

        logger.info(
            "eval_tenant.deleted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="eval_tenant.deleted",
                    message="eval tenant deleted",
                    data={"tenant_id": tenant_id},
                )
            },
        )
