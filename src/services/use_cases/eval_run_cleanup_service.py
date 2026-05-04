"""EvalRunCleanupService — cascade delete de todos los docs asociados a un run_id.

Borra en orden:
1. Para cada doc eval_runs/{run_id}_{shape_name}:
   a. Si el tenant existe y es eval_tenant → delete_eval_tenant (cascade).
   b. Borra el doc de eval_runs y su sub-collection conversations/.
Si alguna sub-operación falla, se loguea y continúa (best-effort).
"""

import src.adapters.outbound.firestore.errors as firestore_errors
import src.infra.logs as app_logs
import src.ports.eval_run_repository_port as eval_run_repository_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.services.dto.eval_run_cleanup_dto as eval_run_cleanup_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.eval_tenant_service as eval_tenant_service_mod

logger = app_logs.get_logger(__name__)


class EvalRunCleanupService:
    def __init__(
        self,
        eval_run_repository: eval_run_repository_port.EvalRunRepositoryPort,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        eval_tenant_service: eval_tenant_service_mod.EvalTenantService,
    ) -> None:
        self._eval_run_repository = eval_run_repository
        self._tenant_repository = tenant_repository
        self._eval_tenant_service = eval_tenant_service

    def delete_eval_run_cascade(self, run_id: str) -> eval_run_cleanup_dto.EvalRunDeleteStatsDTO:
        run_docs = self._eval_run_repository.list_runs_by_run_id(run_id)

        eval_runs_deleted = 0
        tenants_deleted = 0

        for run_doc in run_docs:
            run_doc_id = f"{run_doc.run_id}_{run_doc.shape_name}"

            # --- cascade delete tenant if present and is eval tenant ---
            if run_doc.eval_tenant_id is not None:
                tenant_id = run_doc.eval_tenant_id
                try:
                    tenant = self._tenant_repository.get_by_id(tenant_id)
                    if tenant is not None and tenant.is_eval_tenant:
                        self._eval_tenant_service.delete_eval_tenant(tenant_id)
                        tenants_deleted += 1
                except (
                    service_exceptions.ServiceError,
                    firestore_errors.FirestoreRepositoryError,
                ) as error:
                    logger.warning(
                        "eval_run_cleanup.tenant_delete.failed",
                        extra={
                            "event_data": app_logs.build_log_event(
                                event_name="eval_run_cleanup.tenant_delete.failed",
                                message=str(error),
                                data={
                                    "run_id": run_id,
                                    "run_doc_id": run_doc_id,
                                    "tenant_id": tenant_id,
                                },
                            )
                        },
                    )

            # --- delete eval_run doc + conversations sub-collection ---
            try:
                self._eval_run_repository.delete_run(run_doc_id)
                eval_runs_deleted += 1
            except (
                service_exceptions.ServiceError,
                firestore_errors.FirestoreRepositoryError,
            ) as error:
                logger.warning(
                    "eval_run_cleanup.run_delete.failed",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="eval_run_cleanup.run_delete.failed",
                            message=str(error),
                            data={"run_id": run_id, "run_doc_id": run_doc_id},
                        )
                    },
                )

        logger.info(
            "eval_run_cleanup.completed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="eval_run_cleanup.completed",
                    message="eval run cascade delete completed",
                    data={
                        "run_id": run_id,
                        "eval_runs_deleted": eval_runs_deleted,
                        "tenants_deleted": tenants_deleted,
                    },
                )
            },
        )
        return eval_run_cleanup_dto.EvalRunDeleteStatsDTO(
            eval_runs_deleted=eval_runs_deleted,
            tenants_deleted=tenants_deleted,
        )
