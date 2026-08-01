"""Tests for the SPA catch-all in src/entrypoints/web/static_spa.py.

Each test builds a synthetic build output under tmp_path instead of depending
on a real `npm run build`, and mounts it on a bare FastAPI app.
"""

import pathlib

import fastapi
import fastapi.testclient

import src.entrypoints.web.static_spa as static_spa


def _make_dist(root: pathlib.Path) -> pathlib.Path:
    dist = root / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (dist / "privacy-policy.html").write_text(
        "<!doctype html><title>privacy</title>", encoding="utf-8"
    )
    (assets / "index-abc123.js").write_text("console.log('spa')", encoding="utf-8")
    return dist


def _make_app(dist: pathlib.Path) -> fastapi.FastAPI:
    app = fastapi.FastAPI()

    @app.get("/v1/ping")
    def _ping() -> dict[str, str]:
        return {"status": "ok"}

    static_spa.register_spa_routes(app, dist)
    return app


def test_serves_index_at_root(tmp_path: pathlib.Path) -> None:
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "<title>spa</title>" in response.text


def test_deep_link_falls_back_to_index(tmp_path: pathlib.Path) -> None:
    """A refresh on a client-side route must return the SPA, not a 404."""
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    response = client.get("/agenda/2026-08-01")

    assert response.status_code == 200
    assert "<title>spa</title>" in response.text


def test_registered_api_route_still_wins(tmp_path: pathlib.Path) -> None:
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    response = client.get("/v1/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_path_keeps_its_404(tmp_path: pathlib.Path) -> None:
    """Unmatched API paths must not be masked by the SPA fallback."""
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    for path in ("/v1/does-not-exist", "/healthz", "/oauth/google/callback"):
        response = client.get(path)
        assert response.status_code == 404, path


def test_openapi_schema_is_not_shadowed(tmp_path: pathlib.Path) -> None:
    """FastAPI's own routes keep serving their real payload, not index.html."""
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "openapi" in response.json()


def test_serves_real_static_file(tmp_path: pathlib.Path) -> None:
    """Meta requires privacy-policy.html to stay reachable as a real page."""
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    response = client.get("/privacy-policy.html")

    assert response.status_code == 200
    assert "<title>privacy</title>" in response.text


def test_cache_control_headers(tmp_path: pathlib.Path) -> None:
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    hashed_asset = client.get("/assets/index-abc123.js")
    index = client.get("/")

    assert hashed_asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert index.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"


def test_missing_bundle_is_a_404_not_the_index(tmp_path: pathlib.Path) -> None:
    """Serving index.html for a missing .js would surface as a parse error."""
    client = fastapi.testclient.TestClient(_make_app(_make_dist(tmp_path)))

    response = client.get("/assets/index-deadbeef.js")

    assert response.status_code == 404


def test_no_routes_registered_without_a_build(tmp_path: pathlib.Path) -> None:
    """Local backend development runs without frontend/dist present."""
    empty_dist = tmp_path / "dist"
    empty_dist.mkdir()
    client = fastapi.testclient.TestClient(_make_app(empty_dist))

    assert client.get("/").status_code == 404
    assert client.get("/v1/ping").status_code == 200


def test_traversal_outside_the_build_is_refused(tmp_path: pathlib.Path) -> None:
    """`..` segments must resolve to the SPA fallback, never to a real file."""
    dist = _make_dist(tmp_path)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    assert static_spa._resolve_static_file(dist.resolve(), "../outside.txt") is None
    assert static_spa._resolve_static_file(dist.resolve(), "assets/../../outside.txt") is None
    assert static_spa._resolve_static_file(dist.resolve(), "assets/index-abc123.js") is not None
