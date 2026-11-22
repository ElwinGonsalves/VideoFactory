"""Structured API errors, CORS allow-list, and Title-only slugs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from common.slugs import base_slug, title_slug, unique_slug
from ui import server


@pytest.fixture
def client() -> TestClient:
    return TestClient(server.app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)


def test_error_shape_is_detail_and_hint(client: TestClient) -> None:
    h = {"X-VF-Token": server.TOKEN}
    for res in (client.get("/api/projects/nope-nothing", headers=h), client.get("/api/projects")):
        body = res.json()
        assert set(body) == {"detail", "hint"}
    assert client.get("/api/projects/nope-nothing", headers=h).status_code == 404
    unauth = client.get("/api/projects")
    assert unauth.status_code == 401 and "Reload" in unauth.json()["hint"]


def test_validation_and_server_errors_are_structured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    h = {"X-VF-Token": server.TOKEN}
    res = client.post("/api/analyze", headers=h, content=b"not json")
    assert res.status_code == 422 and res.json()["detail"].startswith("invalid request")

    def boom() -> None:
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(server.jobs, "list", boom)
    res = client.get("/api/jobs", headers=h)
    assert res.status_code == 500
    assert "disk exploded" in res.json()["detail"] and "console" in res.json()["hint"]


def test_cors_allows_only_local_origins(client: TestClient) -> None:
    ask = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-vf-token"}
    ok = client.options("/api/jobs", headers={"Origin": "http://127.0.0.1:8766", **ask})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://127.0.0.1:8766"
    local = client.options("/api/jobs", headers={"Origin": "http://localhost:8765", **ask})
    assert local.headers["access-control-allow-origin"] == "http://localhost:8765"
    for evil in ("https://evil.example", "http://127.0.0.1.evil.example:8765", "http://192.168.1.5:8765"):
        res = client.options("/api/jobs", headers={"Origin": evil, **ask})
        assert "access-control-allow-origin" not in res.headers


def test_slug_comes_from_title_words() -> None:
    assert base_slug("How would the world be if a person never lied?") == "how-world-person-never-lied"
    assert base_slug("Why Costco sells hot dogs for $1.50 (and makes money)") == "why-costco-sells-hot-dogs"
    assert base_slug("To be or not to be") == "to-be-or-not-to"
    assert base_slug("!!!") == "video"
    assert len(base_slug("Extraordinarily " * 10)) <= 48


def test_slug_dedupes_with_numeric_suffix() -> None:
    assert unique_slug("hot-dogs", {"hot-dogs"}) == "hot-dogs-2"
    assert unique_slug("hot-dogs", {"hot-dogs", "hot-dogs-2"}) == "hot-dogs-3"
    assert title_slug("Hot dogs explained", {"hot-dogs-explained"}) == "hot-dogs-explained-2"
