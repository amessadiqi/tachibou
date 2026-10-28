"""Standalone execution runner.

The runner shares the application data directory with the web server and can
record a run while the server is closed. It starts processes directly and does
not invoke a shell.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tachibou.config import ConfigError, get_settings
from tachibou.database import create_db_engine, create_session_factory
from tachibou.migrate import upgrade_database
from tachibou.models import Automation, Execution

Trigger = Literal["manual", "scheduled"]
_SAFE_ID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_safe_id(value: str) -> bool:
    return _SAFE_ID.fullmatch(value) is not None


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def execution_directory(data_dir: Path, execution_id: str) -> Path:
    if not is_safe_id(execution_id):
        raise ValueError("The execution id is not valid.")
    root = (data_dir / "executions").resolve()
    directory = (root / execution_id).resolve()
    if directory.parent != root:
        raise ValueError("The execution id is not valid.")
    return directory


def remove_execution_files(execution_ids: list[str]) -> None:
    data_dir = get_settings().data_dir
    for execution_id in execution_ids:
        if not is_safe_id(execution_id):
            continue
        directory = execution_directory(data_dir, execution_id)
        if directory.is_dir():
            shutil.rmtree(directory)


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def runner_is_alive(pid_path: Path) -> bool:
    try:
        pid = int(pid_path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    return pid_is_running(pid)


def spawn_runner(
    automation_id: str,
    *,
    trigger: Trigger,
    execution_id: str,
    schedule_id: str | None = None,
) -> None:
    command = [
        sys.executable,
        "-m",
        "tachibou.runner",
        "run",
        automation_id,
        "--trigger",
        trigger,
        "--execution-id",
        execution_id,
    ]
    if schedule_id is not None:
        command.extend(["--schedule-id", schedule_id])
    _spawn_detached(command)


def run_execution(
    automation_id: str,
    *,
    trigger: Trigger,
    execution_id: str | None = None,
    schedule_id: str | None = None,
) -> int:
    if not is_safe_id(automation_id):
        print("This automation could not be found.", file=sys.stderr)
        return 1
    if execution_id is not None and not is_safe_id(execution_id):
        print("The execution id is not valid.", file=sys.stderr)
        return 2
    if trigger == "scheduled":
        if schedule_id is None or not is_safe_id(schedule_id):
            print("A scheduled run needs a schedule id.", file=sys.stderr)
            return 2
    else:
        schedule_id = None

    settings = get_settings()
    upgrade_database(settings)
    engine = create_db_engine(settings)
    session = create_session_factory(engine)()
    try:
        return _run_session(
            session,
            settings.data_dir,
            automation_id,
            trigger,
            execution_id or str(uuid4()),
            schedule_id,
        )
    finally:
        session.close()
        engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tachibou-runner",
        description="Run one registered automation and record the result.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run one automation.")
    run.add_argument("automation_id", help="Registered automation identifier.")
    run.add_argument(
        "--trigger",
        required=True,
        choices=("manual", "scheduled"),
        help="Why this execution started.",
    )
    run.add_argument("--execution-id", default=None, help="Stable execution identifier.")
    run.add_argument("--schedule-id", default=None, help="Schedule identifier for a scheduled run.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        return 2
    try:
        return run_execution(
            args.automation_id,
            trigger=args.trigger,
            execution_id=args.execution_id,
            schedule_id=args.schedule_id,
        )
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2


def _run_session(
    session: Session,
    data_dir: Path,
    automation_id: str,
    trigger: Trigger,
    execution_id: str,
    schedule_id: str | None,
) -> int:
    automation = session.get(Automation, automation_id)
    if automation is None:
        print("This automation could not be found.", file=sys.stderr)
        return 1
    if session.get(Execution, execution_id) is not None:
        print("This execution already exists.", file=sys.stderr)
        return 1

    stdout_path = f"executions/{execution_id}/stdout.log"
    stderr_path = f"executions/{execution_id}/stderr.log"
    execution = Execution(
        id=execution_id,
        automation_id=automation_id,
        schedule_id=schedule_id,
        trigger_type=trigger,
        status="running",
        started_at=datetime.now(UTC),
        ended_at=None,
        duration_ms=None,
        exit_code=None,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        error_message=None,
    )
    session.add(execution)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.get(Execution, execution_id) is not None:
            print("This execution already exists.", file=sys.stderr)
            return 1
        _record_not_started(
            session,
            data_dir,
            execution_id,
            automation_id,
            trigger,
            schedule_id,
            stdout_path,
            stderr_path,
            "This automation is already running.",
        )
        return 0

    directory = execution_directory(data_dir, execution_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "stdout.log").touch()
    (directory / "stderr.log").touch()
    (directory / "runner.pid").write_text(str(os.getpid()), encoding="ascii")
    try:
        _launch(automation, data_dir, execution)
    except Exception:
        _mark(execution, status="interrupted", message="The execution stopped before it finished.")
    session.commit()
    return 0


def _record_not_started(
    session: Session,
    data_dir: Path,
    execution_id: str,
    automation_id: str,
    trigger: Trigger,
    schedule_id: str | None,
    stdout_path: str,
    stderr_path: str,
    message: str,
) -> None:
    now = datetime.now(UTC)
    execution = Execution(
        id=execution_id,
        automation_id=automation_id,
        schedule_id=schedule_id,
        trigger_type=trigger,
        status="failed",
        started_at=now,
        ended_at=now,
        duration_ms=0,
        exit_code=None,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        error_message=message,
    )
    session.add(execution)
    session.commit()
    directory = execution_directory(data_dir, execution_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "stdout.log").touch()
    (directory / "stderr.log").touch()


def _launch(automation: Automation, data_dir: Path, execution: Execution) -> None:
    workdir = Path(automation.working_directory).expanduser()
    if not workdir.is_absolute() or not workdir.is_dir():
        _mark(execution, status="failed", message="The working directory could not be found.")
        return
    try:
        command = _command(automation)
    except ValueError:
        _mark(execution, status="failed", message="The arguments are not valid.")
        return

    stdout_path = _stored_file(data_dir, execution.stdout_path)
    stderr_path = _stored_file(data_dir, execution.stderr_path)
    if stdout_path is None or stderr_path is None:
        _mark(execution, status="failed", message="The captured output could not be stored.")
        return
    try:
        with (
            stdout_path.open("ab", buffering=0) as stdout,
            stderr_path.open("ab", buffering=0) as stderr,
        ):
            completed = subprocess.run(
                command,
                cwd=str(workdir),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                check=False,
            )
    except FileNotFoundError:
        _mark(execution, status="failed", message="The executable could not be found.")
        return
    except PermissionError:
        _mark(execution, status="failed", message="The executable could not be started.")
        return
    except OSError:
        _mark(execution, status="failed", message="The executable could not be started.")
        return

    code = completed.returncode
    if code == 0:
        _mark(execution, status="succeeded", exit_code=0)
    elif code < 0:
        _mark(
            execution,
            status="interrupted",
            exit_code=code,
            message="The execution was interrupted.",
        )
    else:
        _mark(execution, status="failed", exit_code=code)


def _command(automation: Automation) -> list[str]:
    arguments = automation.arguments
    if not isinstance(arguments, list) or any(not isinstance(item, str) for item in arguments):
        raise ValueError("The arguments are not valid.")
    executable = automation.executable.strip()
    if not executable:
        raise ValueError("The arguments are not valid.")
    return [executable, *arguments]


def _stored_file(data_dir: Path, stored: str | None) -> Path | None:
    if stored is None or stored == "":
        return None
    root = (data_dir / "executions").resolve()
    candidate = (data_dir / stored).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _mark(
    execution: Execution,
    *,
    status: str,
    exit_code: int | None = None,
    message: str | None = None,
) -> None:
    ended = datetime.now(UTC)
    started = ensure_utc(execution.started_at)
    execution.status = status
    execution.ended_at = ended
    execution.exit_code = exit_code
    execution.error_message = message
    execution.duration_ms = max(0, int((ended - started).total_seconds() * 1000))


def _spawn_detached(command: list[str]) -> None:
    kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def _windows_pid_is_running(pid: int) -> bool:
    import ctypes

    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


if __name__ == "__main__":
    raise SystemExit(main())
