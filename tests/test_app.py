"""HTTP application."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tachibou import __version__
from tachibou.app import create_app


def test_health_reports_a_ready_database(client: TestClient, data_dir: Path) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "name": "Tâchibou",
        "version": __version__,
        "database": "ok",
    }
    assert (data_dir / "tachibou.db").is_file()


def test_api_docs_are_available(client: TestClient) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200


def test_missing_frontend_explains_development_mode(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del data_dir
    monkeypatch.setattr("tachibou.app.bundled_frontend_dir", lambda: tmp_path / "absent")
    with TestClient(create_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "frontend" in response.text.lower()
        assert client.get("/api/health").status_code == 200


def test_serves_the_built_frontend(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del data_dir
    frontend = tmp_path / "frontend"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text(
        "<!doctype html><title>Tâchibou</title><h1>Ready</h1>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr("tachibou.app.bundled_frontend_dir", lambda: frontend)

    with TestClient(create_app()) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Ready" in page.text
        script = client.get("/assets/app.js")
        assert script.status_code == 200
        assert "console.log" in script.text
        route = client.get("/automations")
        assert route.status_code == 200
        assert "Ready" in route.text
        missing_asset = client.get("/assets/missing.js")
        assert missing_asset.status_code == 404
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["content-type"].startswith("application/json")
