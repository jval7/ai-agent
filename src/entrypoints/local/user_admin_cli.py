import argparse
import sys

import pydantic

import src.adapters.outbound.firestore.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.firestore.client_factory as firestore_client_factory
import src.adapters.outbound.firestore.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.firestore.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.secret_manager.app_config_secret_loader_adapter as app_config_secret_loader_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.infra.settings as app_settings
import src.infra.system_adapters as system_adapters
import src.services.dto.user_admin_dto as user_admin_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.user_admin_service as user_admin_service


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local user administration commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-master",
        help="Create or promote a local master user",
    )
    bootstrap_parser.add_argument("--tenant-name", required=True)
    bootstrap_parser.add_argument("--master-email", required=True)
    bootstrap_parser.add_argument("--master-password", required=True)

    create_parser = subparsers.add_parser(
        "create-user",
        help="Create a regular user in the same tenant",
    )
    create_parser.add_argument("--tenant-email", required=True)
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--password", required=True)

    delete_parser = subparsers.add_parser(
        "delete-user",
        help="Delete a regular user by email",
    )
    delete_parser.add_argument("--email", required=True)

    delete_tenant_parser = subparsers.add_parser(
        "delete-tenant",
        help="Delete a tenant and all its data by email",
    )
    delete_tenant_parser.add_argument("--email", required=True)
    delete_tenant_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required flag to confirm destructive operation",
    )

    return parser


def _build_service() -> user_admin_service.UserAdminService:
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


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        service = _build_service()
        if args.command == "bootstrap-master":
            service.bootstrap_master(
                user_admin_dto.BootstrapMasterDTO(
                    tenant_name=args.tenant_name,
                    master_email=args.master_email,
                    master_password=args.master_password,
                )
            )
            print("Master user is ready.")
            return 0

        if args.command == "create-user":
            service.create_user(
                user_admin_dto.CreateUserDTO(
                    tenant_email=args.tenant_email,
                    email=args.email,
                    password=args.password,
                )
            )
            print("User created successfully.")
            return 0

        if args.command == "delete-tenant":
            service.delete_tenant(
                user_admin_dto.DeleteTenantDTO(email=args.email)
            )
            print("Tenant and all its data deleted successfully.")
            return 0

        service.delete_user(
            user_admin_dto.DeleteUserDTO(email=args.email)
        )
        print("User deleted successfully.")
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
