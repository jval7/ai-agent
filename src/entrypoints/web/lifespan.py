"""FastAPI lifespan hook for graceful shutdown.

Lives outside main.py so unit tests can exercise it without triggering the
real AppContainer initialization (which needs Secret Manager + Firestore).
Startup is performed eagerly in `create_app()` (before the lifespan starts);
the shutdown side closes long-lived clients so connections drain cleanly
when Cloud Run sends SIGTERM during a deploy.
"""

import contextlib
import typing

import fastapi

import src.infra.container as app_container
import src.infra.logs as app_logs

logger = app_logs.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> typing.AsyncIterator[None]:
    yield
    container: app_container.AppContainer = app.state.container
    try:
        container.firestore_client.close()
    except Exception as error:
        # best-effort shutdown: never raise from a lifespan close path.
        logger.warning(
            "app.shutdown.firestore_close_failed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="app.shutdown.firestore_close_failed",
                    message="firestore client close raised during shutdown",
                    data={"error": str(error)},
                )
            },
        )
