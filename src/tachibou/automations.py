"""Automation registration.

Registration stores a reference to an existing project. It does not copy or
modify project files. Unregistering removes the Tâchibou record and its
execution history. Schedule removal belongs with scheduling.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.requests import Request

from tachibou.dependencies import DbSession
from tachibou.executions import AutomationActivity, ExecutionSummary, activity_for, summarize
from tachibou.models import Automation, Execution, FileReference
from tachibou.runner import remove_execution_files

FileType = Literal["configuration", "documentation", "log"]
_FILE_TYPE_ORDER = {"configuration": 0, "documentation": 1, "log": 2}
_NAME_LIMIT = 200
_SHORT_LIMIT = 200
_VERSION_LIMIT = 64
_PATH_LIMIT = 1024
_ARGUMENT_LIMIT = 4096


class FieldError(BaseModel):
    field: str
    message: str


class RegistrationError(Exception):
    """The registration could not be saved."""

    def __init__(self, errors: list[FieldError]) -> None:
        self.errors = errors
        super().__init__(errors[0].message if errors else "Check the highlighted fields.")


class NotFoundError(Exception):
    """The automation is not registered."""


class FileReferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_type: FileType
    file_path: str = ""
    label: str | None = None


class AutomationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    description: str | None = None
    owner: str | None = None
    version: str | None = None
    executable: str = ""
    arguments: list[str] = Field(default_factory=list)
    working_directory: str = ""
    entry_point: str | None = None
    file_references: list[FileReferenceIn] = Field(default_factory=list)


class FileReferenceOut(BaseModel):
    id: str
    file_type: FileType
    file_path: str
    label: str | None
    missing: bool


class AutomationOut(BaseModel):
    id: str
    name: str
    description: str | None
    owner: str | None
    version: str | None
    executable: str
    arguments: list[str]
    working_directory: str
    entry_point: str | None
    created_at: datetime
    updated_at: datetime
    configuration_errors: list[str]
    file_references: list[FileReferenceOut]
    running: bool
    latest_execution: ExecutionSummary | None


router = APIRouter(prefix="/api", tags=["automations"])


@router.get("/automations", response_model=list[AutomationOut])
def list_automations(db: DbSession, search: str = "") -> list[AutomationOut]:
    statement = (
        select(Automation)
        .options(selectinload(Automation.file_references))
        .order_by(func.lower(Automation.name), Automation.id)
    )
    needle = search.strip().lower()
    if needle:
        statement = statement.where(func.lower(Automation.name).contains(needle))
    automations = db.scalars(statement).all()
    return _present_many(db, automations)


@router.post("/automations", response_model=AutomationOut, status_code=201)
def create_automation(payload: AutomationWrite, db: DbSession) -> AutomationOut:
    cleaned = _clean(payload)
    now = _utcnow()
    automation = Automation(
        id=str(uuid4()),
        name=cleaned.name,
        description=cleaned.description,
        owner=cleaned.owner,
        version=cleaned.version,
        executable=cleaned.executable,
        arguments=cleaned.arguments,
        working_directory=cleaned.working_directory,
        entry_point=cleaned.entry_point,
        created_at=now,
        updated_at=now,
    )
    _replace_references(automation, cleaned.file_references)
    db.add(automation)
    db.commit()
    db.refresh(automation)
    return _present(db, automation)


@router.get("/automations/{automation_id}", response_model=AutomationOut)
def get_automation(automation_id: str, db: DbSession) -> AutomationOut:
    return _present(db, _get(db, automation_id))


@router.put("/automations/{automation_id}", response_model=AutomationOut)
def update_automation(automation_id: str, payload: AutomationWrite, db: DbSession) -> AutomationOut:
    automation = _get(db, automation_id)
    cleaned = _clean(payload)
    automation.name = cleaned.name
    automation.description = cleaned.description
    automation.owner = cleaned.owner
    automation.version = cleaned.version
    automation.executable = cleaned.executable
    automation.arguments = cleaned.arguments
    automation.working_directory = cleaned.working_directory
    automation.entry_point = cleaned.entry_point
    automation.updated_at = _utcnow()
    _replace_references(automation, cleaned.file_references)
    db.commit()
    db.refresh(automation)
    return _present(db, automation)


@router.delete("/automations/{automation_id}", status_code=204)
def delete_automation(automation_id: str, db: DbSession) -> Response:
    automation = _get(db, automation_id)
    execution_ids = list(
        db.scalars(select(Execution.id).where(Execution.automation_id == automation.id)).all()
    )
    db.delete(automation)
    db.commit()
    remove_execution_files(execution_ids)
    return Response(status_code=204)


def registration_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RegistrationError):
        raise exc
    return JSONResponse(
        status_code=422,
        content={
            "message": "Check the highlighted fields.",
            "errors": [error.model_dump() for error in exc.errors],
        },
    )


def not_found_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, NotFoundError):
        raise exc
    return JSONResponse(status_code=404, content={"message": "This automation could not be found."})


class _Cleaned:
    def __init__(
        self,
        *,
        name: str,
        description: str | None,
        owner: str | None,
        version: str | None,
        executable: str,
        arguments: list[str],
        working_directory: str,
        entry_point: str | None,
        file_references: list[FileReferenceIn],
    ) -> None:
        self.name = name
        self.description = description
        self.owner = owner
        self.version = version
        self.executable = executable
        self.arguments = arguments
        self.working_directory = working_directory
        self.entry_point = entry_point
        self.file_references = file_references


def _clean(payload: AutomationWrite) -> _Cleaned:
    errors: list[FieldError] = []
    name = payload.name.strip()
    executable = payload.executable.strip()
    working_directory = payload.working_directory.strip()
    if not name:
        errors.append(FieldError(field="name", message="Enter a name."))
    elif len(name) > _NAME_LIMIT:
        errors.append(FieldError(field="name", message="Use a shorter name."))
    if not executable:
        errors.append(FieldError(field="executable", message="Enter an executable."))
    elif len(executable) > _PATH_LIMIT:
        errors.append(FieldError(field="executable", message="Use a shorter executable path."))
    if not working_directory:
        errors.append(FieldError(field="working_directory", message="Enter a working directory."))
    elif len(working_directory) > _PATH_LIMIT:
        errors.append(
            FieldError(field="working_directory", message="Use a shorter working directory.")
        )

    arguments: list[str] = []
    for index, argument in enumerate(payload.arguments):
        if not isinstance(argument, str):
            errors.append(
                FieldError(field=f"arguments.{index}", message="Enter each argument as text.")
            )
            continue
        if len(argument) > _ARGUMENT_LIMIT:
            errors.append(FieldError(field=f"arguments.{index}", message="Use a shorter argument."))
            continue
        if argument.strip():
            arguments.append(argument.strip())

    references: list[FileReferenceIn] = []
    for index, reference in enumerate(payload.file_references):
        file_path = reference.file_path.strip()
        if not file_path:
            errors.append(
                FieldError(field=f"file_references.{index}.file_path", message="Enter a file path.")
            )
        elif len(file_path) > _PATH_LIMIT:
            errors.append(
                FieldError(
                    field=f"file_references.{index}.file_path",
                    message="Use a shorter file path.",
                )
            )
        label = _blank_to_none(reference.label)
        if label is not None and len(label) > _SHORT_LIMIT:
            errors.append(
                FieldError(field=f"file_references.{index}.label", message="Use a shorter label.")
            )
        label_ok = label is None or len(label) <= _SHORT_LIMIT
        if file_path and len(file_path) <= _PATH_LIMIT and label_ok:
            references.append(
                FileReferenceIn(file_type=reference.file_type, file_path=file_path, label=label)
            )

    description = _limited_optional(payload.description, "description", 4000, errors)
    owner = _limited_optional(payload.owner, "owner", _SHORT_LIMIT, errors)
    version = _limited_optional(payload.version, "version", _VERSION_LIMIT, errors)
    entry_point = _limited_optional(payload.entry_point, "entry_point", _PATH_LIMIT, errors)
    if errors:
        raise RegistrationError(errors)
    return _Cleaned(
        name=name,
        description=description,
        owner=owner,
        version=version,
        executable=executable,
        arguments=arguments,
        working_directory=working_directory,
        entry_point=entry_point,
        file_references=references,
    )


def _limited_optional(
    value: str | None,
    field: str,
    limit: int,
    errors: list[FieldError],
) -> str | None:
    cleaned = _blank_to_none(value)
    if cleaned is not None and len(cleaned) > limit:
        errors.append(FieldError(field=field, message="Use a shorter value."))
    return cleaned


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _replace_references(automation: Automation, references: list[FileReferenceIn]) -> None:
    automation.file_references.clear()
    for reference in references:
        automation.file_references.append(
            FileReference(
                id=str(uuid4()),
                file_type=reference.file_type,
                file_path=reference.file_path,
                label=reference.label,
            )
        )


def _get(db: Session, automation_id: str) -> Automation:
    statement = (
        select(Automation)
        .options(selectinload(Automation.file_references))
        .where(Automation.id == automation_id)
    )
    automation = db.scalars(statement).one_or_none()
    if automation is None:
        raise NotFoundError
    return automation


def _present(db: Session, automation: Automation) -> AutomationOut:
    return _to_schema(automation, activity_for(db, [automation.id])[automation.id])


def _present_many(db: Session, automations: list[Automation]) -> list[AutomationOut]:
    activities = activity_for(db, [automation.id for automation in automations])
    return [_to_schema(automation, activities[automation.id]) for automation in automations]


def _to_schema(automation: Automation, activity: AutomationActivity) -> AutomationOut:
    references = sorted(
        automation.file_references,
        key=lambda reference: (
            _FILE_TYPE_ORDER.get(reference.file_type, 99),
            reference.file_path.lower(),
            reference.id,
        ),
    )
    return AutomationOut(
        id=automation.id,
        name=automation.name,
        description=automation.description,
        owner=automation.owner,
        version=automation.version,
        executable=automation.executable,
        arguments=list(automation.arguments),
        working_directory=automation.working_directory,
        entry_point=automation.entry_point,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
        configuration_errors=_configuration_errors(automation),
        running=activity.running,
        latest_execution=None if activity.latest is None else summarize(activity.latest),
        file_references=[
            FileReferenceOut(
                id=reference.id,
                file_type=_as_file_type(reference.file_type),
                file_path=reference.file_path,
                label=reference.label,
                missing=not Path(reference.file_path).expanduser().is_file(),
            )
            for reference in references
        ],
    )


def _as_file_type(value: str) -> FileType:
    if value == "documentation":
        return "documentation"
    if value == "log":
        return "log"
    return "configuration"


def _configuration_errors(automation: Automation) -> list[str]:
    errors: list[str] = []
    executable = automation.executable
    executable_path = Path(executable).expanduser()
    if executable_path.is_absolute():
        if not executable_path.is_file():
            errors.append("The executable could not be found.")
    elif "/" in executable or "\\" in executable:
        errors.append("The executable must be an absolute path or a command available on PATH.")
    elif shutil.which(executable) is None:
        errors.append("The executable could not be found.")

    working_directory = Path(automation.working_directory).expanduser()
    if not working_directory.is_absolute():
        errors.append("The working directory must be an absolute path.")
    elif not working_directory.exists():
        errors.append("The working directory could not be found.")
    elif not working_directory.is_dir():
        errors.append("The working directory is not a directory.")

    if automation.entry_point and not Path(automation.entry_point).expanduser().is_file():
        errors.append("The entry point could not be found.")

    for reference in automation.file_references:
        if Path(reference.file_path).expanduser().is_file():
            continue
        label = reference.label or reference.file_path
        errors.append(f'The file "{label}" could not be found.')
    return errors


def _utcnow() -> datetime:
    return datetime.now(UTC)
