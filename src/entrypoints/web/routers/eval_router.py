import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.eval_dto as eval_dto
import src.services.exceptions as service_exceptions

router = fastapi.APIRouter(prefix="/v1/eval", tags=["eval"])


@router.get("/shapes", response_model=eval_dto.ShapesListResponseDTO)
def list_shapes(
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_dto.ShapesListResponseDTO:
    items = container.eval_query_service.list_shapes()
    return eval_dto.ShapesListResponseDTO(items=items)


@router.get("/personas", response_model=eval_dto.PersonasListResponseDTO)
def list_personas(
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_dto.PersonasListResponseDTO:
    items = container.eval_query_service.list_personas()
    return eval_dto.PersonasListResponseDTO(items=items)


@router.get("/prompt-versions", response_model=eval_dto.PromptVersionsListResponseDTO)
def list_prompt_versions(
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_dto.PromptVersionsListResponseDTO:
    items = container.eval_query_service.list_prompt_versions()
    return eval_dto.PromptVersionsListResponseDTO(items=items)


@router.get("/runs", response_model=eval_dto.EvalRunsListResponseDTO)
def list_runs(
    limit: int = 50,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_dto.EvalRunsListResponseDTO:
    items = container.eval_query_service.list_runs(limit=limit)
    return eval_dto.EvalRunsListResponseDTO(items=items)


@router.get("/runs/{run_doc_id}", response_model=eval_dto.EvalRunDetailDTO)
def get_run(
    run_doc_id: str,
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> eval_dto.EvalRunDetailDTO:
    detail = container.eval_query_service.get_run(run_doc_id)
    if detail is None:
        raise service_exceptions.EntityNotFoundError(f"eval run not found: {run_doc_id!r}")
    return detail
