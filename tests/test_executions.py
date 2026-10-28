"""Manual execution, captured output, and history."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tachibou.app import create_app
from tachibou.config import get_settings
from tachibou.database import create_db_engine, create_session_factory
from tachibou.models import Execution
from tachibou.runner import run_execution


def _project(tmp_path: Path, source: str = "print('ok')\n") -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    script = project / "job.py"
    script.write_text(source, encoding="utf-8")
    return project, script


def _register(client: TestClient, project: Path, script: Path, **overrides: object) -> str:
    payload: dict[str, object] = {
        "name": "Nightly report",
        "description": "Builds the nightly report.",
        "executable": sys.executable,
        "arguments": [str(script)],
        "working_directory": str(project),
        "entry_point": str(script),
    }
    payload.update(overrides)
    response = client.post("/api/automations", json=payload)
    assert response.status_code == 201
    return str(response.json()["id"])


def _latest(client: TestClient, automation_id: str) -> dict[str, object]:
    response = client.get(f"/api/automations/{automation_id}/executions")
    assert response.status_code == 200
    return dict(response.json()["items"][0])


def _output(client: TestClient, execution_id: str, stream: str) -> str:
    response = client.get(
        f"/api/executions/{execution_id}/output",
        params={"stream": stream, "offset": 0, "limit": 65536},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["eof"] is True
    return str(body["content"])


def test_python_run_records_success_and_output(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path, "print('hello from python')\n")
    original = script.read_text(encoding="utf-8")
    automation_id = _register(client, project, script)

    assert run_execution(automation_id, trigger="manual") == 0

    history = client.get(f"/api/automations/{automation_id}/executions")
    assert history.status_code == 200
    page = history.json()
    assert page["total"] == 1
    execution = page["items"][0]
    assert execution["status"] == "succeeded"
    assert execution["exit_code"] == 0
    assert execution["trigger_type"] == "manual"
    assert execution["ended_at"] is not None
    assert execution["duration_ms"] is not None
    assert _output(client, execution["id"], "stdout") == "hello from python\n"
    assert script.read_text(encoding="utf-8") == original

    detail = client.get(f"/api/automations/{automation_id}")
    assert detail.json()["running"] is False
    assert detail.json()["latest_execution"]["status"] == "succeeded"


def test_failed_run_keeps_exit_code_and_stderr(client: TestClient, tmp_path: Path) -> None:
    source = "import sys\nsys.stderr.write('boom\\n')\nraise SystemExit(3)\n"
    project, script = _project(tmp_path, source)
    automation_id = _register(client, project, script)

    assert run_execution(automation_id, trigger="manual") == 0

    execution = client.get(f"/api/automations/{automation_id}/executions").json()["items"][0]
    assert execution["status"] == "failed"
    assert execution["exit_code"] == 3
    assert _output(client, execution["id"], "stderr") == "boom\n"
    fetched = client.get(f"/api/executions/{execution['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "failed"


def test_missing_executable_is_a_recorded_failure(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    automation_id = _register(
        client,
        project,
        script,
        executable=str(tmp_path / "missing-command"),
    )

    assert run_execution(automation_id, trigger="manual") == 0
    health = client.get("/api/health")
    assert health.status_code == 200

    execution = client.get(f"/api/automations/{automation_id}/executions").json()["items"][0]
    assert execution["status"] == "failed"
    assert execution["exit_code"] is None
    assert execution["error_message"] == "The executable could not be found."


def test_arguments_are_not_interpreted_by_a_shell(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(
        tmp_path,
        "import json, sys\nfrom pathlib import Path\n"
        "Path('argv.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
    )
    arguments = [str(script), "hello && rm", "$(whoami)"]
    automation_id = _register(client, project, script, arguments=arguments)

    assert run_execution(automation_id, trigger="manual") == 0

    recorded = json.loads((project / "argv.json").read_text(encoding="utf-8"))
    assert recorded == ["hello && rm", "$(whoami)"]
    execution = client.get(f"/api/automations/{automation_id}/executions").json()["items"][0]
    assert execution["status"] == "succeeded"


def test_powershell_and_batch_use_the_same_runner(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path, "print('python-example')\n")
    python_id = _register(client, project, script, name="Python example")
    assert run_execution(python_id, trigger="manual") == 0
    python_run = client.get(f"/api/automations/{python_id}/executions").json()["items"][0]
    assert python_run["status"] == "succeeded"
    assert "python-example" in _output(client, python_run["id"], "stdout")

    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is not None:
        powershell_id = _register(
            client,
            project,
            script,
            name="PowerShell example",
            executable=shell,
            arguments=["-NoProfile", "-Command", "Write-Output powershell-example"],
        )
        assert run_execution(powershell_id, trigger="manual") == 0
        powershell_run = _latest(client, powershell_id)
        assert powershell_run["status"] == "succeeded"
        assert "powershell-example" in _output(client, powershell_run["id"], "stdout")

    command = shutil.which("cmd")
    if command is not None:
        batch = project / "hello.bat"
        batch.write_text("@echo batch-example\r\n", encoding="utf-8")
        batch_id = _register(
            client,
            project,
            script,
            name="Batch example",
            executable=command,
            arguments=["/c", str(batch)],
        )
        assert run_execution(batch_id, trigger="manual") == 0
        batch_run = client.get(f"/api/automations/{batch_id}/executions").json()["items"][0]
        assert batch_run["status"] == "succeeded"
        assert "batch-example" in _output(client, batch_run["id"], "stdout")


def test_scheduled_trigger_is_distinct(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    automation_id = _register(client, project, script)
    schedule_id = str(uuid4())

    assert run_execution(automation_id, trigger="scheduled", schedule_id=schedule_id) == 0

    execution = client.get(f"/api/automations/{automation_id}/executions").json()["items"][0]
    assert execution["trigger_type"] == "scheduled"
    assert execution["schedule_id"] == schedule_id
    manual = client.get(f"/api/automations/{automation_id}/executions").json()["items"]
    assert [item["trigger_type"] for item in manual] == ["scheduled"]


def test_history_is_newest_first_and_paginated(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path, "import sys\nprint(sys.argv[1])\n")
    automation_id = _register(client, project, script, arguments=[str(script), "one"])
    for label in ("one", "two", "three"):
        client.put(
            f"/api/automations/{automation_id}",
            json={
                "name": "Nightly report",
                "executable": sys.executable,
                "arguments": [str(script), label],
                "working_directory": str(project),
            },
        )
        assert run_execution(automation_id, trigger="manual") == 0

    first = client.get(
        f"/api/automations/{automation_id}/executions",
        params={"limit": 2, "offset": 0},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2
    assert _output(client, body["items"][0]["id"], "stdout").strip() == "three"
    assert _output(client, body["items"][1]["id"], "stdout").strip() == "two"

    second = client.get(
        f"/api/automations/{automation_id}/executions",
        params={"limit": 2, "offset": 2},
    )
    assert _output(client, second.json()["items"][0]["id"], "stdout").strip() == "one"


def test_history_survives_restart(data_dir: Path, tmp_path: Path) -> None:
    del data_dir
    project, script = _project(tmp_path, "print('kept')\n")
    with TestClient(create_app()) as client:
        automation_id = _register(client, project, script)
        assert run_execution(automation_id, trigger="manual") == 0
        execution_id = _latest(client, automation_id)["id"]

    with TestClient(create_app()) as restarted:
        loaded = restarted.get(f"/api/executions/{execution_id}")
        assert loaded.status_code == 200
        assert loaded.json()["status"] == "succeeded"
        assert _output(restarted, execution_id, "stdout") == "kept\n"


def test_runner_cli_works_without_the_server(data_dir: Path, tmp_path: Path) -> None:
    project, script = _project(tmp_path, "print('from-cli')\n")
    with TestClient(create_app()) as client:
        automation_id = _register(client, project, script)

    completed = subprocess.run(
        [sys.executable, "-m", "tachibou.runner", "run", automation_id, "--trigger", "manual"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "TACHIBOU_DATA_DIR": str(data_dir)},
    )
    assert completed.returncode == 0, completed.stderr

    with TestClient(create_app()) as client:
        execution = client.get(f"/api/automations/{automation_id}/executions").json()["items"][0]
        assert execution["status"] == "succeeded"
        assert _output(client, execution["id"], "stdout") == "from-cli\n"


def test_manual_request_returns_while_the_command_is_still_running(
    client: TestClient, tmp_path: Path
) -> None:
    source = "import time\nprint('started', flush=True)\ntime.sleep(2)\n"
    project, script = _project(tmp_path, source)
    automation_id = _register(client, project, script)

    started = time.monotonic()
    accepted = client.post(f"/api/automations/{automation_id}/executions")
    elapsed = time.monotonic() - started
    assert accepted.status_code == 202
    assert elapsed < 1
    execution_id = accepted.json()["id"]
    assert client.get("/api/health").status_code == 200

    deadline = time.monotonic() + 15
    saw_running = False
    status = ""
    while time.monotonic() < deadline:
        response = client.get(f"/api/executions/{execution_id}")
        if response.status_code == 200:
            status = response.json()["status"]
            if status == "running":
                saw_running = True
                assert client.get("/api/health").status_code == 200
            if status in {"succeeded", "failed", "interrupted"}:
                break
        time.sleep(0.05)

    assert saw_running
    assert status == "succeeded"


def test_second_run_is_rejected_while_one_is_running(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path, "import time\ntime.sleep(2)\n")
    automation_id = _register(client, project, script)
    first_id = str(uuid4())
    worker = Thread(
        target=run_execution,
        args=(automation_id,),
        kwargs={"trigger": "manual", "execution_id": first_id},
    )
    worker.start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response = client.get(f"/api/executions/{first_id}")
            if response.status_code == 200 and response.json()["status"] == "running":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("The first execution did not start.")

        rejected = client.post(f"/api/automations/{automation_id}/executions")
        assert rejected.status_code == 409
        assert rejected.json()["message"] == "This automation is already running."

        second_id = str(uuid4())
        assert (
            run_execution(
                automation_id,
                trigger="manual",
                execution_id=second_id,
            )
            == 0
        )
        second = client.get(f"/api/executions/{second_id}")
        assert second.json()["status"] == "failed"
        assert second.json()["error_message"] == "This automation is already running."
    finally:
        worker.join(timeout=15)

    finished = client.get(f"/api/executions/{first_id}")
    assert finished.json()["status"] == "succeeded"


def test_output_is_read_in_chunks_and_missing_files_are_explained(
    client: TestClient, tmp_path: Path
) -> None:
    project, script = _project(tmp_path, "print('abcdefghij', end='')\n")
    automation_id = _register(client, project, script)
    assert run_execution(automation_id, trigger="manual") == 0
    execution_id = str(_latest(client, automation_id)["id"])

    first = client.get(
        f"/api/executions/{execution_id}/output",
        params={"stream": "stdout", "offset": 0, "limit": 4},
    )
    assert first.status_code == 200
    assert first.json()["content"] == "abcd"
    assert first.json()["eof"] is False
    assert first.json()["next_offset"] == 4

    second = client.get(
        f"/api/executions/{execution_id}/output",
        params={"stream": "stdout", "offset": 4, "limit": 4},
    )
    assert second.json()["content"] == "efgh"

    stored = get_settings().data_dir / "executions" / execution_id / "stderr.log"
    stored.unlink()
    missing = client.get(
        f"/api/executions/{execution_id}/output",
        params={"stream": "stderr"},
    )
    assert missing.status_code == 404
    assert missing.json()["message"] == "The captured output is not available."


def test_output_paths_cannot_escape_the_data_directory(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    automation_id = _register(client, project, script)
    assert run_execution(automation_id, trigger="manual") == 0
    execution_id = str(_latest(client, automation_id)["id"])

    engine = create_db_engine(get_settings())
    session: Session = create_session_factory(engine)()
    try:
        execution = session.get(Execution, execution_id)
        assert execution is not None
        execution.stdout_path = "../../etc/passwd"
        session.commit()
    finally:
        session.close()
        engine.dispose()

    response = client.get(
        f"/api/executions/{execution_id}/output",
        params={"stream": "stdout"},
    )
    assert response.status_code == 404
    assert response.json()["message"] == "The captured output is not available."
    assert "root:" not in response.text


def test_stale_running_record_is_marked_interrupted(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    automation_id = _register(client, project, script)
    execution_id = str(uuid4())
    engine = create_db_engine(get_settings())
    session = create_session_factory(engine)()
    try:
        session.add(
            Execution(
                id=execution_id,
                automation_id=automation_id,
                schedule_id=None,
                trigger_type="manual",
                status="running",
                started_at=datetime.now(UTC) - timedelta(minutes=5),
                ended_at=None,
                duration_ms=None,
                exit_code=None,
                stdout_path=f"executions/{execution_id}/stdout.log",
                stderr_path=f"executions/{execution_id}/stderr.log",
                error_message=None,
            )
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()

    loaded = client.get(f"/api/executions/{execution_id}")
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "interrupted"
    assert loaded.json()["error_message"] == "The execution stopped before it finished."


def test_live_runner_is_not_marked_interrupted(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path)
    automation_id = _register(client, project, script)
    execution_id = str(uuid4())
    directory = get_settings().data_dir / "executions" / execution_id
    directory.mkdir(parents=True)
    (directory / "runner.pid").write_text(str(os.getpid()), encoding="ascii")
    engine = create_db_engine(get_settings())
    session = create_session_factory(engine)()
    try:
        session.add(
            Execution(
                id=execution_id,
                automation_id=automation_id,
                schedule_id=None,
                trigger_type="manual",
                status="running",
                started_at=datetime.now(UTC) - timedelta(minutes=5),
                ended_at=None,
                duration_ms=None,
                exit_code=None,
                stdout_path=None,
                stderr_path=None,
                error_message=None,
            )
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()

    loaded = client.get(f"/api/executions/{execution_id}")
    assert loaded.json()["status"] == "running"
    listed = client.get("/api/automations").json()
    match = next(item for item in listed if item["id"] == automation_id)
    assert match["running"] is True


def test_unregister_removes_history_and_keeps_project_files(
    client: TestClient, tmp_path: Path
) -> None:
    project, script = _project(tmp_path, "print('stay')\n")
    automation_id = _register(client, project, script)
    assert run_execution(automation_id, trigger="manual") == 0
    execution_id = str(_latest(client, automation_id)["id"])
    log_dir = get_settings().data_dir / "executions" / execution_id
    assert log_dir.is_dir()

    deleted = client.delete(f"/api/automations/{automation_id}")
    assert deleted.status_code == 204
    assert script.is_file()
    assert script.read_text(encoding="utf-8") == "print('stay')\n"
    assert not log_dir.exists()
    assert client.get(f"/api/executions/{execution_id}").status_code == 404


def test_unknown_execution_returns_a_plain_error(client: TestClient) -> None:
    response = client.get(f"/api/executions/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["message"] == "This execution could not be found."


def test_runs_do_not_overwrite_earlier_records(client: TestClient, tmp_path: Path) -> None:
    project, script = _project(tmp_path, "print('first')\n")
    automation_id = _register(client, project, script)
    assert run_execution(automation_id, trigger="manual") == 0
    script.write_text("print('second')\n", encoding="utf-8")
    assert run_execution(automation_id, trigger="manual") == 0

    items = client.get(f"/api/automations/{automation_id}/executions").json()["items"]
    assert len(items) == 2
    outputs = {_output(client, item["id"], "stdout").strip() for item in items}
    assert outputs == {"first", "second"}
    engine = create_db_engine(get_settings())
    session = create_session_factory(engine)()
    try:
        stored = session.scalars(
            select(Execution).where(Execution.automation_id == automation_id)
        ).all()
        assert len(stored) == 2
    finally:
        session.close()
        engine.dispose()
