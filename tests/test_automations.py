"""Automation registration."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from tachibou.app import create_app


def _project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    script = project / "job.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    return project, script


def _payload(project: Path, script: Path, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Nightly report",
        "description": "Builds the nightly report.",
        "owner": "Ada",
        "version": "1.2.0",
        "executable": sys.executable,
        "arguments": [str(script.name)],
        "working_directory": str(project),
        "entry_point": str(script),
        "file_references": [
            {
                "file_type": "documentation",
                "file_path": str(script),
                "label": "Job",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_register_edit_and_unregister_without_touching_files(
    client: TestClient, tmp_path: Path
) -> None:
    project, script = _project(tmp_path)
    original = script.read_text(encoding="utf-8")

    created = client.post("/api/automations", json=_payload(project, script))
    assert created.status_code == 201
    body = created.json()
    assert body["id"]
    assert body["arguments"] == ["job.py"]
    assert body["configuration_errors"] == []
    assert body["file_references"][0]["missing"] is False
    assert script.read_text(encoding="utf-8") == original

    updated = client.put(
        f"/api/automations/{body['id']}",
        json=_payload(project, script, executable=sys.executable, arguments=["--quiet"]),
    )
    assert updated.status_code == 200
    assert updated.json()["arguments"] == ["--quiet"]
    assert script.read_text(encoding="utf-8") == original

    deleted = client.delete(f"/api/automations/{body['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/automations/{body['id']}").status_code == 404
    assert script.read_text(encoding="utf-8") == original
    assert script.is_file()


def test_registration_persists_across_restart(data_dir: Path, tmp_path: Path) -> None:
    del data_dir
    project, script = _project(tmp_path)
    with TestClient(create_app()) as first:
        created = first.post("/api/automations", json=_payload(project, script))
        assert created.status_code == 201
        automation_id = created.json()["id"]

    with TestClient(create_app()) as second:
        loaded = second.get(f"/api/automations/{automation_id}")
        assert loaded.status_code == 200
        assert loaded.json()["name"] == "Nightly report"
    assert script.is_file()


def test_required_fields_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/automations",
        json={
            "name": "   ",
            "executable": "",
            "working_directory": "",
            "arguments": [],
        },
    )
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"name", "executable", "working_directory"}
    assert client.get("/api/automations").json() == []


def test_missing_executable_is_reported_and_saved(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    response = client.post(
        "/api/automations",
        json=_payload(project, script, executable="missing-command-xyz"),
    )
    assert response.status_code == 201
    assert response.json()["configuration_errors"] == ["The executable could not be found."]


def test_invalid_working_directory_is_reported(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    response = client.post(
        "/api/automations",
        json=_payload(project, script, working_directory=str(script)),
    )
    assert response.status_code == 201
    assert "The working directory is not a directory." in response.json()["configuration_errors"]


def test_missing_file_reference_is_marked(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    missing = project / "missing.toml"
    response = client.post(
        "/api/automations",
        json=_payload(
            project,
            script,
            file_references=[
                {"file_type": "configuration", "file_path": str(missing), "label": "Settings"}
            ],
        ),
    )
    assert response.status_code == 201
    reference = response.json()["file_references"][0]
    assert reference["missing"] is True
    assert 'The file "Settings" could not be found.' in response.json()["configuration_errors"]
    assert not missing.exists()


def test_search_matches_name(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    client.post("/api/automations", json=_payload(project, script, name="Nightly report"))
    client.post("/api/automations", json=_payload(project, script, name="Morning cleanup"))

    matches = client.get("/api/automations", params={"search": "night"})
    assert matches.status_code == 200
    assert [item["name"] for item in matches.json()] == ["Nightly report"]


def test_unknown_automation_returns_a_plain_error(client: TestClient) -> None:
    response = client.get("/api/automations/missing")
    assert response.status_code == 404
    assert response.json()["message"] == "This automation could not be found."
