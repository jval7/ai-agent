import argparse
import logging
import os
import secrets
import string
import sys

import pydantic

import src.adapters.outbound.email_resend.logging_email_notifier_adapter as logging_email_notifier_adapter
import src.adapters.outbound.email_resend.resend_email_notifier_adapter as resend_email_notifier_adapter
import src.adapters.outbound.firestore.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.firestore.client_factory as firestore_client_factory
import src.adapters.outbound.firestore.invitation_token_repository_adapter as invitation_token_repository_adapter
import src.adapters.outbound.firestore.refresh_token_repository_adapter as refresh_token_repository_adapter
import src.adapters.outbound.firestore.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.firestore.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.secret_manager.app_config_secret_loader_adapter as app_config_secret_loader_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.infra.settings as app_settings
import src.infra.system_adapters as system_adapters
import src.ports.email_notifier_port as email_notifier_port
import src.services.dto.user_admin_dto as user_admin_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.auth_service as auth_service_mod
import src.services.use_cases.invitation_service as invitation_service_mod
import src.services.use_cases.user_admin_service as user_admin_service


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Professional administration commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser(
        "create-professional",
        help="Create a new professional (tenant + user + agent profile)",
    )
    create_parser.add_argument("--tenant-name", required=True)
    create_parser.add_argument("--email", required=True)

    reset_parser = subparsers.add_parser(
        "reset-password",
        help="Reset a professional's password",
    )
    reset_parser.add_argument("--email", required=True)

    delete_parser = subparsers.add_parser(
        "delete-professional",
        help="Delete a professional and all their data",
    )
    delete_parser.add_argument("--email", required=True)
    delete_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required flag to confirm destructive operation",
    )

    subparsers.add_parser(
        "list-professionals",
        help="List all professionals (email, tenant, role, active, created_at)",
    )

    invite_parser = subparsers.add_parser(
        "invite-professional",
        help="Create a professional and send an email invitation to set up their password",
    )
    invite_parser.add_argument("--tenant-name", required=True)
    invite_parser.add_argument("--email", required=True)
    invite_parser.add_argument("--professional-name", default=None)

    return parser


def _print_professionals_table(
    summaries: list[user_admin_dto.ProfessionalSummaryDTO],
) -> None:
    if not summaries:
        print("No professionals found.")
        return

    headers: list[str] = [
        "EMAIL",
        "TENANT",
        "ROLE",
        "ACTIVE",
        "CREATED_AT",
        "USER_ID",
        "TENANT_ID",
    ]
    rows: list[list[str]] = []
    for summary in summaries:
        rows.append(
            [
                summary.email,
                summary.tenant_name,
                summary.role,
                "yes" if summary.is_active else "no",
                summary.created_at.isoformat(),
                summary.user_id,
                summary.tenant_id,
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            if len(cell) > widths[index]:
                widths[index] = len(cell)

    def _format_row(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    separator = ["-" * width for width in widths]
    print(_format_row(headers))
    print(_format_row(separator))
    for row in rows:
        print(_format_row(row))
    print(f"\nTotal: {len(rows)} professional(s)")


def _build_settings_and_firestore() -> tuple[app_settings.Settings, object]:
    app_config_loader = app_config_secret_loader_adapter.SecretManagerAppConfigLoaderAdapter()
    loaded_secret = app_config_loader.load()
    settings = app_settings.Settings.from_secret_json(
        raw_app_config_json=loaded_secret.secret_json,
        adc_project_id=loaded_secret.project_id,
    )
    firestore_client = firestore_client_factory.build_client(
        project_id=settings.google_cloud_project_id,
        database_id=settings.firestore_database_id,
    )
    return settings, firestore_client


def _build_service() -> user_admin_service.UserAdminService:
    settings, firestore_client = _build_settings_and_firestore()
    tenant_repository = tenant_repository_adapter.FirestoreTenantRepositoryAdapter(firestore_client)
    user_repository = user_repository_adapter.FirestoreUserRepositoryAdapter(firestore_client)
    agent_profile_repository = (
        agent_profile_repository_adapter.FirestoreAgentProfileRepositoryAdapter(firestore_client)
    )
    return user_admin_service.UserAdminService(
        tenant_repository=tenant_repository,
        user_repository=user_repository,
        agent_profile_repository=agent_profile_repository,
        password_hasher=password_hasher_adapter.Pbkdf2PasswordHasherAdapter(),
        id_generator=system_adapters.UuidIdGeneratorAdapter(),
        clock=system_adapters.SystemClockAdapter(),
        default_system_prompt=settings.default_system_prompt,
    )


def _build_service_with_invitation() -> tuple[
    user_admin_service.UserAdminService,
    email_notifier_port.EmailNotifierPort,
    app_settings.Settings,
]:
    settings, firestore_client = _build_settings_and_firestore()
    tenant_repo = tenant_repository_adapter.FirestoreTenantRepositoryAdapter(firestore_client)
    user_repo = user_repository_adapter.FirestoreUserRepositoryAdapter(firestore_client)
    agent_profile_repo = agent_profile_repository_adapter.FirestoreAgentProfileRepositoryAdapter(
        firestore_client
    )
    refresh_token_repo = refresh_token_repository_adapter.FirestoreRefreshTokenRepositoryAdapter(
        firestore_client
    )
    invitation_token_repo = (
        invitation_token_repository_adapter.FirestoreInvitationTokenRepositoryAdapter(
            firestore_client
        )
    )
    hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    id_gen = system_adapters.UuidIdGeneratorAdapter()
    clock = system_adapters.SystemClockAdapter()

    notifier: email_notifier_port.EmailNotifierPort
    if settings.email_notifier_enabled and settings.resend_api_key:
        notifier = resend_email_notifier_adapter.ResendEmailNotifierAdapter(settings=settings)
    else:
        notifier = logging_email_notifier_adapter.LoggingEmailNotifierAdapter()

    import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter_mod

    jwt_provider = jwt_provider_adapter_mod.Hs256JwtProviderAdapter(
        secret=settings.jwt_secret,
        clock=clock,
    )

    import src.adapters.outbound.firestore.agent_profile_repository_adapter as ap_adapter
    import src.adapters.outbound.firestore.user_repository_adapter as u_adapter

    auth_svc = auth_service_mod.AuthService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=hasher,
        jwt_provider=jwt_provider,
        refresh_token_repository=refresh_token_repo,
        id_generator=id_gen,
        clock=clock,
        default_system_prompt=settings.default_system_prompt,
        access_ttl_seconds=settings.jwt_access_ttl_seconds,
        refresh_ttl_seconds=settings.jwt_refresh_ttl_seconds,
    )
    del ap_adapter, u_adapter

    inv_service = invitation_service_mod.InvitationService(
        invitation_token_repository=invitation_token_repo,
        user_repository=user_repo,
        tenant_repository=tenant_repo,
        password_hasher=hasher,
        email_notifier=notifier,
        id_generator=id_gen,
        clock=clock,
        refresh_token_repository=refresh_token_repo,
        auth_service=auth_svc,
        frontend_app_base_url=settings.frontend_app_base_url,
        account_setup_ttl_hours=settings.invitation_account_setup_ttl_hours,
        password_reset_ttl_minutes=settings.invitation_password_reset_ttl_minutes,
    )

    service = user_admin_service.UserAdminService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=hasher,
        id_generator=id_gen,
        clock=clock,
        default_system_prompt=settings.default_system_prompt,
        invitation_service=inv_service,
    )
    return service, notifier, settings


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "invite-professional":
            logging.basicConfig(
                level=logging.INFO,
                format="[%(levelname)s] %(name)s: %(message)s",
                stream=sys.stderr,
                force=True,
            )
            service, notifier, settings = _build_service_with_invitation()
            notifier_class = type(notifier).__name__
            print("--- diagnostic ---", file=sys.stderr)
            print(
                f"  GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT', '<unset>')}",
                file=sys.stderr,
            )
            print(
                f"  google_cloud_project_id (from secret): {settings.google_cloud_project_id}",
                file=sys.stderr,
            )
            print(f"  email_notifier_enabled: {settings.email_notifier_enabled}", file=sys.stderr)
            print(
                f"  resend_api_key set: {bool(settings.resend_api_key)} (len={len(settings.resend_api_key) if settings.resend_api_key else 0})",
                file=sys.stderr,
            )
            print(f"  resend_from_email: {settings.resend_from_email!r}", file=sys.stderr)
            print(f"  resend_from_name: {settings.resend_from_name!r}", file=sys.stderr)
            print(f"  email_notifier class: {notifier_class}", file=sys.stderr)
            print(f"  frontend_app_base_url: {settings.frontend_app_base_url}", file=sys.stderr)
            print("------------------", file=sys.stderr)

            service.invite_professional(
                user_admin_dto.InviteProfessionalDTO(
                    tenant_name=args.tenant_name,
                    email=args.email,
                    professional_name=args.professional_name,
                )
            )
            if notifier_class == "ResendEmailNotifierAdapter":
                print("Invitation sent via Resend.")
                print(f"  Tenant: {args.tenant_name}")
                print(f"  Email:  {args.email}")
                print("Check Resend dashboard at https://resend.com/emails for delivery status.")
            else:
                print("WARNING: Logging adapter is active — NO real email was sent.")
                print(f"  Notifier: {notifier_class}")
                print(f"  Tenant: {args.tenant_name}")
                print(f"  Email:  {args.email}")
                print("The invitation link was logged above. To send real emails, ensure")
                print("RESEND_API_KEY is set in the secret and EMAIL_NOTIFIER_ENABLED=true.")
            return 0

        service = _build_service()
        if args.command == "create-professional":
            alphabet = string.ascii_letters + string.digits
            password = "".join(secrets.choice(alphabet) for _ in range(16))
            service.create_professional(
                user_admin_dto.CreateProfessionalDTO(
                    tenant_name=args.tenant_name,
                    email=args.email,
                    password=password,
                )
            )
            print("Professional created successfully.")
            print(f"  Tenant:   {args.tenant_name}")
            print(f"  Email:    {args.email}")
            print(f"  Password: {password}")
            print(f"GENERATED_PASSWORD={password}")
            return 0

        if args.command == "reset-password":
            alphabet = string.ascii_letters + string.digits
            password = "".join(secrets.choice(alphabet) for _ in range(16))
            service.reset_password(
                user_admin_dto.ResetPasswordDTO(
                    email=args.email,
                    new_password=password,
                )
            )
            print("Password reset successfully.")
            print(f"  Email:    {args.email}")
            print(f"  Password: {password}")
            print(f"GENERATED_PASSWORD={password}")
            return 0

        if args.command == "list-professionals":
            summaries = service.list_professionals()
            _print_professionals_table(summaries)
            return 0

        service.delete_professional(user_admin_dto.DeleteProfessionalDTO(email=args.email))
        print("Professional and all their data deleted successfully.")
        return 0
    except pydantic.ValidationError as error:
        print(f"Validation error: {error}", file=sys.stderr)
        return 1
    except service_exceptions.ServiceError as error:
        print(f"Operation failed: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
