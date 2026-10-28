"""Manual execution history and captured output.

The runner creates each execution record and writes stdout and stderr to files.
These routes start that runner and read the records back. They do not wait for
the automation to finish.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from tachibou.config import get_settings
from tachibou.dependencies import DbSession
from tachibou.models import Automation, Execution
from tachibou.runner import (
    Trigger,
    ensure_utc,
    execution_directory,
    runner_is_alive,
    spawn_runner,
)

Status = Literal["running", "succeeded", "failed", "interrupted"]
Stream = Literal["stdout", "stderr"]
_OUTPUT_LIMIT = 65_536
_STALE_GRACE = timedelta(seconds=15)


class AlreadyRunningError(Exception):
    """A manual run was requested while this automation is already running."""


class ExecutionNotFoundError(Exception):
    """The execution record does not exist."""


class OutputUnavailableError(Exception):
    """Captured output cannot be read."""


class ExecutionSummary(BaseModel):
    id: str
    status: Status
    trigger_type: Trigger
    started_at: datetime
    ended_at: datetime | None
    exit_code: int | None


class ExecutionOut(BaseModel):
    id: str
    automation_id: str
    schedule_id: str | None
    trigger_type: Trigger
    status: Status
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    exit_code: int | None
    stdout_path: str | None
    stderr_path: str | None
    error_message: str | None


class ExecutionAccepted(BaseModel):
    id: str
    automation_id: str
    status: Literal["running"]


class ExecutionPage(BaseModel):
    items: list[ExecutionOut]
    total: int
    limit: int
    offset: int


class OutputPage(BaseModel):
    stream: Stream
    offset: int
    next_offset: int
    size: int
    eof: bool
    content: str


@dataclass(frozen=True)
class AutomationActivity:
    running: bool
    latest: Execution | None


router = APIRouter(prefix="/api", tags=["executions"])


@router.post(
    "/automations/{automation_id}/executions",
    response_model=ExecutionAccepted,
    status_code=202,
)
def start_execution(automation_id: str, db: DbSession) -> ExecutionAccepted:
    _require_automation(db, automation_id)
    reconcile_stale_executions(db)
    running = db.scalar(
        select(Execution.id).where(
            Execution.automation_id == automation_id,
            Execution.status == "running",
        )
    )
    if running is not None:
        raise AlreadyRunningError
    execution_id = str(uuid4())
    spawn_runner(automation_id, trigger="manual", execution_id=execution_id)
    return ExecutionAccepted(id=execution_id, automation_id=automation_id, status="running")


@router.get("/automations/{automation_id}/executions", response_model=ExecutionPage)
def list_executions(
    automation_id: str,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ExecutionPage:
    _require_automation(db, automation_id)
    reconcile_stale_executions(db)
    total = db.scalar(
        select(func.count()).select_from(Execution).where(Execution.automation_id == automation_id)
    )
    rows = db.scalars(
        select(Execution)
        .where(Execution.automation_id == automation_id)
        .order_by(Execution.started_at.desc(), Execution.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ExecutionPage(
        items=[_to_schema(row) for row in rows],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionOut)
def get_execution(execution_id: str, db: DbSession) -> ExecutionOut:
    reconcile_stale_executions(db)
    return _to_schema(_get(db, execution_id))


@router.get("/executions/{execution_id}/output", response_model=OutputPage)
def read_output(
    execution_id: str,
    db: DbSession,
    stream: Stream,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=_OUTPUT_LIMIT, ge=1, le=_OUTPUT_LIMIT),
) -> OutputPage:
    execution = _get(db, execution_id)
    stored = execution.stdout_path if stream == "stdout" else execution.stderr_path
    path = _output_file(stored)
    if path is None or not path.is_file():
        raise OutputUnavailableError
    size = path.stat().st_size
    bounded = min(offset, size)
    with path.open("rb") as handle:
        handle.seek(bounded)
        payload = handle.read(limit)
    return OutputPage(
        stream=stream,
        offset=bounded,
        next_offset=bounded + len(payload),
        size=size,
        eof=bounded + len(payload) >= size,
        content=payload.decode("utf-8", errors="replace"),
    )


def activity_for(db: Session, automation_ids: list[str]) -> dict[str, AutomationActivity]:
    reconcile_stale_executions(db)
    result = {
        automation_id: AutomationActivity(running=False, latest=None)
        for automation_id in automation_ids
    }
    if not automation_ids:
        return result
    running_ids = set(
        db.scalars(
            select(Execution.automation_id).where(
                Execution.automation_id.in_(automation_ids),
                Execution.status == "running",
            )
        ).all()
    )
    latest_started = (
        select(
            Execution.automation_id.label("automation_id"),
            func.max(Execution.started_at).label("started_at"),
        )
        .where(Execution.automation_id.in_(automation_ids))
        .group_by(Execution.automation_id)
        .subquery()
    )
    rows = db.scalars(
        select(Execution).join(
            latest_started,
            (Execution.automation_id == latest_started.c.automation_id)
            & (Execution.started_at == latest_started.c.started_at),
        )
    ).all()
    latest: dict[str, Execution] = {}
    for row in rows:
        current = latest.get(row.automation_id)
        if current is None or row.id > current.id:
            latest[row.automation_id] = row
    for automation_id in automation_ids:
        result[automation_id] = AutomationActivity(
            running=automation_id in running_ids,
            latest=latest.get(automation_id),
        )
    return result


def reconcile_stale_executions(db: Session) -> None:
    data_dir = get_settings().data_dir
    now = datetime.now(UTC)
    changed = False
    running = db.scalars(select(Execution).where(Execution.status == "running")).all()
    for execution in running:
        if _still_running(data_dir, execution, now):
            continue
        _mark_interrupted(execution, now)
        changed = True
    if changed:
        db.commit()


def already_running_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AlreadyRunningError):
        raise exc
    return JSONResponse(
        status_code=409,
        content={"message": "This automation is already running."},
    )


def execution_not_found_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ExecutionNotFoundError):
        raise exc
    return JSONResponse(status_code=404, content={"message": "This execution could not be found."})


def output_unavailable_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, OutputUnavailableError):
        raise exc
    return JSONResponse(
        status_code=404,
        content={"message": "The captured output is not available."},
    )


def _require_automation(db: Session, automation_id: str) -> None:
    from tachibou.automations import NotFoundError

    exists = db.scalar(select(Automation.id).where(Automation.id == automation_id))
    if exists is None:
        raise NotFoundError


def _get(db: Session, execution_id: str) -> Execution:
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise ExecutionNotFoundError
    return execution


def summarize(execution: Execution) -> ExecutionSummary:
    return ExecutionSummary(
        id=execution.id,
        status=_status(execution.status),
        trigger_type=_trigger(execution.trigger_type),
        started_at=ensure_utc(execution.started_at),
        ended_at=None if execution.ended_at is None else ensure_utc(execution.ended_at),
        exit_code=execution.exit_code,
    )


def _to_schema(execution: Execution) -> ExecutionOut:
    summary = summarize(execution)
    return ExecutionOut(
        id=summary.id,
        automation_id=execution.automation_id,
        schedule_id=execution.schedule_id,
        trigger_type=summary.trigger_type,
        status=summary.status,
        started_at=summary.started_at,
        ended_at=summary.ended_at,
        duration_ms=execution.duration_ms,
        exit_code=summary.exit_code,
        stdout_path=execution.stdout_path,
        stderr_path=execution.stderr_path,
        error_message=execution.error_message,
    )


def _still_running(data_dir: Path, execution: Execution, now: datetime) -> bool:
    if not _safe_directory_name(execution.id):
        return False
    pid_path = execution_directory(data_dir, execution.id) / "runner.pid"
    if pid_path.is_file():
        return runner_is_alive(pid_path)
    return now - ensure_utc(execution.started_at) < _STALE_GRACE


def _safe_directory_name(execution_id: str) -> bool:
    try:
        execution_directory(get_settings().data_dir, execution_id)
    except ValueError:
        return False
    return True


def _mark_interrupted(execution: Execution, now: datetime) -> None:
    execution.status = "interrupted"
    execution.ended_at = now
    execution.error_message = "The execution stopped before it finished."
    execution.duration_ms = max(
        0,
        int((now - ensure_utc(execution.started_at)).total_seconds() * 1000),
    )


def _output_file(stored: str | None) -> Path | None:
    if stored is None or stored == "":
        return None
    data_dir = get_settings().data_dir
    root = (data_dir / "executions").resolve()
    candidate = (data_dir / stored).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _trigger(value: str) -> Trigger:
    if value == "scheduled":
        return "scheduled"
    return "manual"


def _status(value: str) -> Status:
    if value == "succeeded":
        return "succeeded"
    if value == "failed":
        return "failed"
    if value == "interrupted":
        return "interrupted"
    return "running"
