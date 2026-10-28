# AGENTS.md

Guidance for people and coding agents working on Tâchibou.

## Purpose

Tâchibou is a local dashboard for managing independent automations on one Windows machine. It will register existing scripts, run them, schedule them with Windows Task Scheduler, and record what happened.

It is not a workflow engine. Automations stay independent: they do not import a Tâchibou SDK, and Tâchibou does not coordinate them with each other.

## Architectural boundaries

- Python package in `src/tachibou`. FastAPI serves HTTP. React, TypeScript, and Vite live in `frontend/`.
- SQLite, SQLAlchemy, and Alembic handle persistence. The database file lives in the application data directory, outside the repository.
- The production frontend is compiled into the Python wheel and served by FastAPI. Node.js is for development and builds only.
- Bind to `127.0.0.1` by default. Do not add accounts, remote workers, cloud services, or a custom scheduling engine.
- The standalone runner records executions without the web server. Windows Task Scheduler comes later. Do not add scheduling while implementing an unrelated change.
- Keep future platform-specific code isolated. The domain model stays platform-independent.
- Do not launch commands through a shell unless a later feature explicitly requires it.
- Add a module when a feature needs it. Do not create empty packages for future use.
- Persistence currently covers `app_metadata`, `automation`, `file_reference`, and `execution`. Add the schedule table with scheduling. Captured output lives in files under the data directory, not in SQLite.
- Unregistering deletes the Tâchibou record and its execution history. It does not change project files. Removing a Windows schedule belongs with the scheduling work, and a failure there must stop the deletion.

## Development commands

Install the backend in editable mode from the repository root:

```powershell
python -m pip install -e ".[dev]"
```

```powershell
ruff check .
ruff format .
pytest
tachibou version
tachibou start
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
```

Build a wheel. This requires Node.js:

```powershell
python -m build --wheel
```

Create a migration after changing models:

```powershell
alembic revision --autogenerate -m "describe the change"
```

`TACHIBOU_DATA_DIR` selects the database location for the application and for Alembic.

## Code conventions

- Use type hints on Python functions.
- Format and lint Python with Ruff. Target Python 3.11 or newer.
- Keep HTTP handlers small. Keep persistence beside the models until a feature needs another module.
- Prefer functional React components and Tailwind utilities. Keep TypeScript strict.
- Store future timestamps in UTC and convert them to local time in the interface.
- Write user-facing errors in plain language.
- Do not store credentials or captured logs in the database. Execution logs will be files when execution exists.

## Testing expectations

- Add or update tests for every behavioral change.
- Backend tests use pytest and a temporary `TACHIBOU_DATA_DIR`.
- Frontend tests use Vitest.
- Report the commands you ran and their actual results.
- Do not claim a check passed if it was not run.

## Git workflow

- `main` is the stable branch.
- Create a short-lived feature branch for each change.
- Open a pull request. Continuous integration must pass before merging.
- Prefer squash merges.
- Use Conventional Commits, for example `feat:`, `fix:`, `test:`, `docs:`, and `chore:`.

## AI agent rules

- Work on an isolated branch and stay inside the assigned scope.
- Avoid unrelated changes.
- Do not commit secrets, credentials, or private planning documents.
- If the private product requirements are not available locally, ask for access. Do not invent requirements.
- Do not copy private planning documents into the repository, issues, or pull requests. Document only behavior that is actually implemented.
- Do not publish releases, push, or change repository security settings unless the user explicitly asks.
