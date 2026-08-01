"""Serves the built React SPA from the same Cloud Run service as the API.

Replaces the load balancer + CDN + GCS bucket setup: the SPA travels inside the
backend image, so there is a single origin (no CORS) and no fixed-cost
infrastructure. Any GET that does not match an API route falls back to
index.html, which is what client-side routing (BrowserRouter) needs so a deep
link like /agenda survives a page refresh.
"""

import pathlib

import fastapi
import fastapi.responses as fastapi_responses

import src.infra.logs as app_logs

logger = app_logs.get_logger(__name__)

# Path prefixes owned by the API. Requests under these keep their real 404
# instead of receiving index.html, so a mistyped endpoint still looks broken
# rather than silently returning a page.
_API_PATH_PREFIXES = (
    "v1/",
    "oauth/",
    "healthz",
    "readyz",
    "docs",
    "redoc",
    "openapi.json",
)

_INDEX_FILE_NAME = "index.html"
_HASHED_ASSETS_DIR = "assets"

# Vite fingerprints everything under assets/, so those files can be cached
# forever. index.html must never be cached or a deploy would keep serving the
# previous build's asset references.
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_NO_CACHE_CONTROL = "no-cache, max-age=0, must-revalidate"

# src/entrypoints/web/static_spa.py -> repo root (/app inside the image).
DEFAULT_STATIC_ROOT = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "dist"


def register_spa_routes(
    app: fastapi.FastAPI,
    static_root: pathlib.Path = DEFAULT_STATIC_ROOT,
) -> None:
    """Register the SPA catch-all route.

    No-op when the build output is missing, which is the normal case for local
    backend development (the SPA runs on the Vite dev server instead).
    Must be called after every API router so those routes win the match.
    """
    index_file = static_root / _INDEX_FILE_NAME
    if not index_file.is_file():
        logger.info(
            "app.spa.disabled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="app.spa.disabled",
                    message="frontend build not found; serving API only",
                    data={"static_root": str(static_root)},
                )
            },
        )
        return

    resolved_root = static_root.resolve()

    @app.get("/{spa_path:path}", include_in_schema=False)
    def serve_spa(spa_path: str) -> fastapi_responses.FileResponse:
        if _is_api_path(spa_path):
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_404_NOT_FOUND)

        static_file = _resolve_static_file(resolved_root, spa_path)
        if static_file is None:
            # Un bundle faltante debe fallar como bundle: devolver index.html
            # haria que el navegador parsee HTML como JS ("Unexpected token
            # '<'") y esconderia un deploy incompleto detras de un error raro.
            if spa_path.startswith(f"{_HASHED_ASSETS_DIR}/"):
                raise fastapi.HTTPException(status_code=fastapi.status.HTTP_404_NOT_FOUND)
            return fastapi_responses.FileResponse(
                index_file,
                headers={"cache-control": _NO_CACHE_CONTROL},
            )
        return fastapi_responses.FileResponse(
            static_file,
            headers={"cache-control": _cache_control_for(spa_path)},
        )

    logger.info(
        "app.spa.enabled",
        extra={
            "event_data": app_logs.build_log_event(
                event_name="app.spa.enabled",
                message="serving SPA from the backend service",
                data={"static_root": str(resolved_root)},
            )
        },
    )


def _is_api_path(spa_path: str) -> bool:
    return spa_path.startswith(_API_PATH_PREFIXES)


def _resolve_static_file(resolved_root: pathlib.Path, spa_path: str) -> pathlib.Path | None:
    """Return the real file for `spa_path`, or None to fall back to index.html.

    Resolving before the containment check is what stops `../` traversal from
    reaching files outside the build output.
    """
    if spa_path == "":
        return None
    try:
        candidate = (resolved_root / spa_path).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.is_relative_to(resolved_root):
        return None
    if not candidate.is_file():
        return None
    return candidate


def _cache_control_for(spa_path: str) -> str:
    if spa_path.startswith(f"{_HASHED_ASSETS_DIR}/"):
        return _IMMUTABLE_CACHE_CONTROL
    return _NO_CACHE_CONTROL
