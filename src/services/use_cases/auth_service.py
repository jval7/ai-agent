import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.jwt_provider_port as jwt_provider_port
import src.ports.password_hasher_port as password_hasher_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.user_repository_port as user_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class AuthService:
    def __init__(
        self,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        user_repository: user_repository_port.UserRepositoryPort,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        password_hasher: password_hasher_port.PasswordHasherPort,
        jwt_provider: jwt_provider_port.JwtProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        default_system_prompt: str,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> None:
        self._tenant_repository = tenant_repository
        self._user_repository = user_repository
        self._agent_profile_repository = agent_profile_repository
        self._password_hasher = password_hasher
        self._jwt_provider = jwt_provider
        self._id_generator = id_generator
        self._clock = clock
        self._default_system_prompt = default_system_prompt
        self._access_ttl_seconds = access_ttl_seconds
        self._refresh_ttl_seconds = refresh_ttl_seconds

    def register(self, register_dto: auth_dto.RegisterUserDTO) -> auth_dto.AuthTokensDTO:
        existing_user = self._user_repository.get_by_email(register_dto.email.lower())
        if existing_user is not None:
            logger.warning(
                "auth.register.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.register.failed",
                        message="register failed",
                        data={
                            "reason": "email_already_registered",
                            "email_domain": self._resolve_email_domain(register_dto.email),
                        },
                    )
                },
            )
            raise service_exceptions.InvalidStateError("email is already registered")

        now_value = self._clock.now()
        tenant_id = self._id_generator.new_id()
        user_id = self._id_generator.new_id()

        tenant = tenant_entity.Tenant(
            id=tenant_id,
            name=register_dto.tenant_name,
            created_at=now_value,
            updated_at=now_value,
        )
        self._tenant_repository.save(tenant)

        password_hash = self._password_hasher.hash_password(register_dto.password)
        user = user_entity.User(
            id=user_id,
            tenant_id=tenant_id,
            email=register_dto.email,
            password_hash=password_hash,
            role=service_constants.DEFAULT_OWNER_ROLE,
            is_active=True,
            created_at=now_value,
        )
        self._user_repository.save(user)

        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt=self._default_system_prompt,
            updated_at=now_value,
        )
        self._agent_profile_repository.save(agent_profile)

        auth_tokens = self._issue_auth_tokens(user)
        logger.info(
            "auth.register.success",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="auth.register.success",
                    message="register succeeded",
                    data={
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "role": user.role,
                    },
                )
            },
        )
        return auth_tokens

    def login(self, login_dto: auth_dto.LoginDTO) -> auth_dto.AuthTokensDTO:
        user = self._user_repository.get_by_email(login_dto.email.lower())
        if user is None:
            logger.warning(
                "auth.login.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.login.failed",
                        message="login failed",
                        data={
                            "reason": "invalid_credentials",
                            "email_domain": self._resolve_email_domain(login_dto.email),
                        },
                    )
                },
            )
            raise service_exceptions.AuthenticationError("invalid credentials")

        if not user.is_active:
            logger.warning(
                "auth.login.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.login.failed",
                        message="login failed",
                        data={
                            "reason": "inactive_user",
                            "tenant_id": user.tenant_id,
                            "user_id": user.id,
                        },
                    )
                },
            )
            raise service_exceptions.AuthenticationError("user is inactive")

        password_valid = self._password_hasher.verify_password(
            login_dto.password, user.password_hash
        )
        if not password_valid:
            logger.warning(
                "auth.login.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.login.failed",
                        message="login failed",
                        data={
                            "reason": "invalid_credentials",
                            "tenant_id": user.tenant_id,
                            "user_id": user.id,
                        },
                    )
                },
            )
            raise service_exceptions.AuthenticationError("invalid credentials")

        auth_tokens = self._issue_auth_tokens(user)
        logger.info(
            "auth.login.success",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="auth.login.success",
                    message="login succeeded",
                    data={
                        "tenant_id": user.tenant_id,
                        "user_id": user.id,
                        "role": user.role,
                    },
                )
            },
        )
        return auth_tokens

    def refresh(self, refresh_dto: auth_dto.RefreshTokenDTO) -> auth_dto.AuthTokensDTO:
        claims = self._jwt_provider.decode(refresh_dto.refresh_token)
        if claims.token_kind != "refresh":
            logger.warning(
                "auth.refresh.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.refresh.failed",
                        message="refresh failed",
                        data={
                            "reason": "invalid_token_kind",
                            "token_kind": claims.token_kind,
                        },
                    )
                },
            )
            raise service_exceptions.AuthenticationError("token is not a refresh token")

        user = self._user_repository.get_by_id(claims.sub)
        if user is None:
            logger.warning(
                "auth.refresh.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.refresh.failed",
                        message="refresh failed",
                        data={
                            "reason": "user_not_found",
                            "tenant_id": claims.tenant_id,
                            "user_id": claims.sub,
                        },
                    )
                },
            )
            raise service_exceptions.AuthenticationError("user not found")

        if user.tenant_id != claims.tenant_id:
            logger.warning(
                "auth.refresh.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="auth.refresh.failed",
                        message="refresh failed",
                        data={
                            "reason": "tenant_mismatch",
                            "tenant_id": claims.tenant_id,
                            "user_id": claims.sub,
                        },
                    )
                },
            )
            raise service_exceptions.AuthenticationError("token tenant mismatch")

        self._jwt_provider.revoke_refresh_jti(claims.jti)
        auth_tokens = self._issue_auth_tokens(user)
        logger.info(
            "auth.refresh.success",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="auth.refresh.success",
                    message="refresh succeeded",
                    data={
                        "tenant_id": user.tenant_id,
                        "user_id": user.id,
                    },
                )
            },
        )
        return auth_tokens

    def logout(self, logout_dto: auth_dto.LogoutDTO) -> None:
        claims = self._jwt_provider.decode(logout_dto.refresh_token)
        if claims.token_kind != "refresh":
            raise service_exceptions.AuthenticationError("token is not a refresh token")
        self._jwt_provider.revoke_refresh_jti(claims.jti)

    def authenticate_access_token(self, access_token: str) -> auth_dto.TokenClaimsDTO:
        claims = self._jwt_provider.decode(access_token)
        if claims.token_kind != "access":
            raise service_exceptions.AuthenticationError("token is not an access token")
        return claims

    def _resolve_email_domain(self, email: str) -> str:
        normalized_email = email.strip().lower()
        email_segments = normalized_email.split("@", maxsplit=1)
        if len(email_segments) != 2:
            return ""
        return email_segments[1]

    def _issue_auth_tokens(self, user: user_entity.User) -> auth_dto.AuthTokensDTO:
        access_claims = self._build_claims(
            user=user,
            token_kind="access",
            ttl_seconds=self._access_ttl_seconds,
        )
        refresh_claims = self._build_claims(
            user=user,
            token_kind="refresh",
            ttl_seconds=self._refresh_ttl_seconds,
        )
        access_token = self._jwt_provider.encode(access_claims)
        refresh_token = self._jwt_provider.encode(refresh_claims)
        return auth_dto.AuthTokensDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_seconds=self._access_ttl_seconds,
        )

    def _build_claims(
        self,
        user: user_entity.User,
        token_kind: str,
        ttl_seconds: int,
    ) -> auth_dto.TokenClaimsDTO:
        current_epoch = self._clock.now_epoch_seconds()
        return auth_dto.TokenClaimsDTO(
            sub=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
            exp=current_epoch + ttl_seconds,
            jti=self._id_generator.new_id(),
            token_kind=token_kind,
        )
