import asyncio
import time

import fastapi

import src.entrypoints.web.dependencies as dependencies
import src.infra.container as app_container
import src.services.dto.health_dto as health_dto

router = fastapi.APIRouter(tags=["health"])

_FIRESTORE_TIMEOUT_SECONDS = 1.5


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=health_dto.ReadinessResponseDTO)
async def readyz(
    response: fastapi.Response,
    container: app_container.AppContainer = fastapi.Depends(dependencies.get_container),
) -> health_dto.ReadinessResponseDTO:
    checks: list[health_dto.DependencyStatusDTO] = []

    firestore_check = await _check_firestore(container)
    checks.append(firestore_check)

    has_errors = any(c.status == "error" for c in checks)
    overall_status = "degraded" if has_errors else "ok"

    if has_errors:
        response.status_code = fastapi.status.HTTP_503_SERVICE_UNAVAILABLE

    return health_dto.ReadinessResponseDTO(status=overall_status, checks=checks)


async def _check_firestore(
    container: app_container.AppContainer,
) -> health_dto.DependencyStatusDTO:
    start = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(
            loop.run_in_executor(
                None,
                # Firestore rechaza los ids que abren y cierran con "__": son
                # reservados. Con "__health__" este check fallaba siempre y
                # /readyz respondia 503 de forma permanente.
                lambda: container.firestore_client.collection("health_check").limit(1).get(),
            ),
            timeout=_FIRESTORE_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return health_dto.DependencyStatusDTO(name="firestore", status="ok", latency_ms=elapsed_ms)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return health_dto.DependencyStatusDTO(
            name="firestore", status="error", latency_ms=elapsed_ms, message=str(exc)
        )
