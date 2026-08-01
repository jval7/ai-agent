"""Tests for the FastAPI lifespan hook in src/entrypoints/web/lifespan.py.

We exercise the lifespan context manager directly with a synthetic FastAPI
app that exposes a mock container — the real AppContainer needs Firestore +
Secret Manager and is not viable in unit tests.
"""

import logging
import typing
import unittest.mock

import fastapi
import fastapi.testclient
import pytest

import src.entrypoints.web.lifespan as lifespan_module

_LOGGER_NAME = "src.entrypoints.web.lifespan"


def _make_app_with_lifespan(
    container: typing.Any,
) -> fastapi.FastAPI:
    app = fastapi.FastAPI(lifespan=lifespan_module.lifespan)
    app.state.container = container

    @app.get("/_ping")
    def _ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_lifespan_closes_firestore_client_on_shutdown() -> None:
    container = unittest.mock.MagicMock()
    container.firestore_client = unittest.mock.MagicMock()
    app = _make_app_with_lifespan(container)

    with fastapi.testclient.TestClient(app) as client:
        response = client.get("/_ping")
        assert response.status_code == 200
        # Shutdown not yet fired — close() should not have been called.
        container.firestore_client.close.assert_not_called()

    # Exiting the TestClient context fires the shutdown side of lifespan.
    container.firestore_client.close.assert_called_once_with()


def test_lifespan_swallows_close_failures(caplog: pytest.LogCaptureFixture) -> None:
    container = unittest.mock.MagicMock()
    container.firestore_client = unittest.mock.MagicMock()
    container.firestore_client.close.side_effect = RuntimeError("simulated close failure")
    app = _make_app_with_lifespan(container)
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    # Lifespan must not raise during shutdown — best-effort cleanup.
    with fastapi.testclient.TestClient(app) as client:
        client.get("/_ping")

    container.firestore_client.close.assert_called_once_with()
    failure_events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "app.shutdown.firestore_close_failed" in failure_events
