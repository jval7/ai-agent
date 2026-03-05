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
        help="Create a regular user using master credentials",
    )
    create_parser.add_argument("--master-email", required=True)
    create_parser.add_argument("--master-password", required=True)
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--password", required=True)

    delete_parser = subparsers.add_parser(
        "delete-user",
        help="Delete a regular user using master credentials",
    )
    delete_parser.add_argument("--master-email", required=True)
    delete_parser.add_argument("--master-password", required=True)
    delete_parser.add_argument("--email", required=True)

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
            bootstrap_request = user_admin_dto.BootstrapMasterDTO(
                tenant_name=args.tenant_name,
                master_email=args.master_email,
                master_password=args.master_password,
            )
            service.bootstrap_master(bootstrap_request)
            print("Master user is ready.")
            return 0
        if args.command == "create-user":
            create_request = user_admin_dto.CreateUserByMasterDTO(
                master_email=args.master_email,
                master_password=args.master_password,
                email=args.email,
                password=args.password,
            )
            service.create_user(create_request)
            print("User created successfully.")
            return 0

        delete_request = user_admin_dto.DeleteUserByMasterDTO(
            master_email=args.master_email,
            master_password=args.master_password,
            email=args.email,
        )
        service.delete_user(delete_request)
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
