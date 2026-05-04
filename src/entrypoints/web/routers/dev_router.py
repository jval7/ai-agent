import hmac

import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.dev_dto as dev_dto
import src.services.dto.eval_run_cleanup_dto as eval_run_cleanup_dto
import src.services.dto.eval_tenant_dto as eval_tenant_dto
import src.services.exceptions as service_exceptions

router = fastapi.APIRouter(prefix="/v1/dev", tags=["dev"])


def _require_eval_admin_secret(
    request: fastapi.Request,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    configured_secret = container.settings.eval_admin_secret
    if not configured_secret:
        raise service_exceptions.AuthenticationError("eval admin secret is not configured")
    provided_secret = request.headers.get("X-Eval-Admin-Secret")
    if not provided_secret or not hmac.compare_digest(provided_secret, configured_secret):
        raise service_exceptions.AuthenticationError(
            "invalid or missing X-Eval-Admin-Secret header"
        )


@router.post("/memory/reset", response_model=dev_dto.MemoryResetResponseDTO)
def reset_memory(
    _: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> dev_dto.MemoryResetResponseDTO:
    return container.memory_admin_service.reset_memory()


@router.post("/memory/chat/reset", response_model=dev_dto.MemoryResetResponseDTO)
def reset_chat_memory(
    _: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> dev_dto.MemoryResetResponseDTO:
    return container.memory_admin_service.reset_chat_memory()


@router.post(
    "/eval-tenants",
    response_model=eval_tenant_dto.EvalTenantCreatedDTO,
    status_code=201,
)
def create_eval_tenant(
    body: eval_tenant_dto.CreateEvalTenantRequestDTO,
    _: None = fastapi.Depends(_require_eval_admin_secret),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_tenant_dto.EvalTenantCreatedDTO:
    return container.eval_tenant_service.create_eval_tenant(
        run_id=body.run_id,
        shape_name=body.shape_name,
    )


@router.delete(
    "/eval-tenants/{tenant_id}",
    status_code=204,
)
def delete_eval_tenant(
    tenant_id: str,
    _: None = fastapi.Depends(_require_eval_admin_secret),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.eval_tenant_service.delete_eval_tenant(tenant_id)


@router.delete(
    "/eval-runs/{run_id}",
    response_model=eval_run_cleanup_dto.EvalRunDeleteStatsDTO,
)
def delete_eval_run(
    run_id: str,
    _: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_run_cleanup_dto.EvalRunDeleteStatsDTO:
    """Borra una corrida (todos sus shape docs + tenants efimeros). Solo
    requiere JWT de cualquier tenant logueado (no el EVAL_ADMIN_SECRET) —
    el dashboard se accede desde la app autenticada y borrar un run es una
    operacion legitima para cualquier dev en el ambiente.

    Los endpoints `/eval-tenants` siguen requiriendo secret porque crean
    tenants efimeros (operacion de runner, no de dashboard).
    """
    return container.eval_run_cleanup_service.delete_eval_run_cascade(run_id)
