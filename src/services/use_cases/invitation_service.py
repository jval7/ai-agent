import datetime
import hashlib
import secrets

import src.domain.entities.invitation_token as invitation_token_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.email_notifier_port as email_notifier_port
import src.ports.id_generator_port as id_generator_port
import src.ports.invitation_token_repository_port as invitation_token_repository_port
import src.ports.password_hasher_port as password_hasher_port
import src.ports.refresh_token_repository_port as refresh_token_repository_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.user_repository_port as user_repository_port
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service_mod

logger = app_logs.get_logger(__name__)


class InvitationService:
    def __init__(
        self,
        invitation_token_repository: invitation_token_repository_port.InvitationTokenRepositoryPort,
        user_repository: user_repository_port.UserRepositoryPort,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        password_hasher: password_hasher_port.PasswordHasherPort,
        email_notifier: email_notifier_port.EmailNotifierPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        refresh_token_repository: refresh_token_repository_port.RefreshTokenRepositoryPort,
        auth_service: auth_service_mod.AuthService,
        frontend_app_base_url: str,
        account_setup_ttl_hours: int,
        password_reset_ttl_minutes: int,
    ) -> None:
        self._invitation_token_repository = invitation_token_repository
        self._user_repository = user_repository
        self._tenant_repository = tenant_repository
        self._password_hasher = password_hasher
        self._email_notifier = email_notifier
        self._id_generator = id_generator
        self._clock = clock
        self._refresh_token_repository = refresh_token_repository
        self._auth_service = auth_service
        self._frontend_app_base_url = frontend_app_base_url
        self._account_setup_ttl_hours = account_setup_ttl_hours
        self._password_reset_ttl_minutes = password_reset_ttl_minutes

    def issue_account_setup_invitation(
        self,
        user: user_entity.User,
        tenant: tenant_entity.Tenant,
    ) -> None:
        now = self._clock.now()
        self._invitation_token_repository.invalidate_active_for_user(
            user_id=user.id,
            purpose=invitation_token_entity.InvitationPurpose.ACCOUNT_SETUP,
            now=now,
        )
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = now + datetime.timedelta(hours=self._account_setup_ttl_hours)

        invitation_token = invitation_token_entity.InvitationToken(
            token_hash=token_hash,
            user_id=user.id,
            tenant_id=user.tenant_id,
            purpose=invitation_token_entity.InvitationPurpose.ACCOUNT_SETUP,
            expires_at=expires_at,
            consumed_at=None,
            created_at=now,
        )
        self._invitation_token_repository.save(invitation_token)

        invitation_url = f"{self._frontend_app_base_url}/accept-invite?token={raw_token}"
        self._email_notifier.send_account_invitation(
            to_email=user.email,
            to_name=None,
            invitation_url=invitation_url,
            tenant_name=tenant.name,
        )
        logger.info(
            "invitation.account_setup.issued",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="invitation.account_setup.issued",
                    message="account setup invitation issued",
                    data={
                        "user_id": user.id,
                        "tenant_id": user.tenant_id,
                    },
                )
            },
        )

    def accept_account_setup(
        self,
        token: str,
        new_password: str,
    ) -> auth_dto.AuthTokensDTO:
        now = self._clock.now()
        token_hash = _hash_token(token)
        consumed_record = self._invitation_token_repository.consume(
            token_hash=token_hash,
            consumed_at=now,
        )
        if consumed_record is None:
            raise service_exceptions.AuthenticationError(
                "invitation link is expired or already used"
            )
        if consumed_record.purpose != invitation_token_entity.InvitationPurpose.ACCOUNT_SETUP:
            raise service_exceptions.AuthenticationError("invitation link is for the wrong purpose")

        user = self._user_repository.get_by_id(consumed_record.user_id)
        if user is None:
            raise service_exceptions.EntityNotFoundError("user not found")

        updated_user = user.model_copy(deep=True)
        updated_user.password_hash = self._password_hasher.hash_password(new_password)
        updated_user.is_active = True
        self._user_repository.save(updated_user)

        auth_tokens = self._auth_service.issue_session_tokens_for_user(updated_user)

        tenant = self._tenant_repository.get_by_id(updated_user.tenant_id)
        tenant_name = tenant.name if tenant is not None else ""
        login_url = self._frontend_app_base_url

        try:
            self._email_notifier.send_welcome(
                to_email=updated_user.email,
                to_name=None,
                tenant_name=tenant_name,
                login_url=login_url,
            )
        except service_exceptions.ExternalProviderError as error:
            logger.warning(
                "invitation.welcome_email.failed",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="invitation.welcome_email.failed",
                        message="welcome email failed but account setup succeeded",
                        data={
                            "user_id": updated_user.id,
                            "error": str(error),
                        },
                    )
                },
            )

        logger.info(
            "invitation.account_setup.accepted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="invitation.account_setup.accepted",
                    message="account setup accepted",
                    data={
                        "user_id": updated_user.id,
                        "tenant_id": updated_user.tenant_id,
                    },
                )
            },
        )
        return auth_tokens

    def request_password_reset(self, email: str) -> None:
        normalized_email = email.strip().lower()
        user = self._user_repository.get_by_email(normalized_email)
        if user is None:
            logger.info(
                "invitation.password_reset.anti_enum",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="invitation.password_reset.anti_enum",
                        message=("password reset requested for unknown email (anti-enumeration)"),
                        data={},
                    )
                },
            )
            return

        now = self._clock.now()
        self._invitation_token_repository.invalidate_active_for_user(
            user_id=user.id,
            purpose=invitation_token_entity.InvitationPurpose.PASSWORD_RESET,
            now=now,
        )
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = now + datetime.timedelta(minutes=self._password_reset_ttl_minutes)

        reset_token = invitation_token_entity.InvitationToken(
            token_hash=token_hash,
            user_id=user.id,
            tenant_id=user.tenant_id,
            purpose=invitation_token_entity.InvitationPurpose.PASSWORD_RESET,
            expires_at=expires_at,
            consumed_at=None,
            created_at=now,
        )
        self._invitation_token_repository.save(reset_token)

        reset_url = f"{self._frontend_app_base_url}/reset-password?token={raw_token}"
        self._email_notifier.send_password_reset(
            to_email=user.email,
            reset_url=reset_url,
        )
        logger.info(
            "invitation.password_reset.issued",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="invitation.password_reset.issued",
                    message="password reset token issued",
                    data={
                        "user_id": user.id,
                        "tenant_id": user.tenant_id,
                    },
                )
            },
        )

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        now = self._clock.now()
        token_hash = _hash_token(token)
        consumed_record = self._invitation_token_repository.consume(
            token_hash=token_hash,
            consumed_at=now,
        )
        if consumed_record is None:
            raise service_exceptions.AuthenticationError(
                "password reset link is expired or already used"
            )
        if consumed_record.purpose != invitation_token_entity.InvitationPurpose.PASSWORD_RESET:
            raise service_exceptions.AuthenticationError(
                "password reset link is for the wrong purpose"
            )

        user = self._user_repository.get_by_id(consumed_record.user_id)
        if user is None:
            raise service_exceptions.EntityNotFoundError("user not found")

        updated_user = user.model_copy(deep=True)
        updated_user.password_hash = self._password_hasher.hash_password(new_password)
        self._user_repository.save(updated_user)

        self._refresh_token_repository.revoke_all_for_user(
            user_id=updated_user.id,
            now=now,
        )
        logger.info(
            "invitation.password_reset.confirmed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="invitation.password_reset.confirmed",
                    message="password reset confirmed",
                    data={
                        "user_id": updated_user.id,
                        "tenant_id": updated_user.tenant_id,
                    },
                )
            },
        )


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
