# Tâchibou

One nest for all your automations.

Tâchibou is a lightweight, self-hosted dashboard for managing independent automations on a single Windows machine. It is meant to register scripts you already have, run them, schedule them with Windows Task Scheduler, and show whether they succeeded.

Tâchibou does not replace those automations or orchestrate workflows between them.

## Current development status

Version 0.1 is in early development. You can register automations that already exist on this computer, run them manually, and review what happened without changing their files.

What works:

- An installable `tachibou` command and a local FastAPI service bound to `127.0.0.1`
- A React interface for the automation list, registration, detail, and execution pages
- SQLite persistence with Alembic migrations
- Validation for required fields, with a clear report when an executable, working directory, or referenced file cannot be found
- Manual execution through the `tachibou-runner` command, including captured output and execution history

`tachibou-runner run <automation-id> --trigger manual` runs one registered automation without the web server. Give it `--trigger scheduled --schedule-id <schedule-id>` when a schedule starts it. The runner does not use a shell: register `powershell` or `cmd` as the executable when a script needs one.

Windows is the intended runtime. The current build also runs on other systems so it can be developed and tested before Task Scheduler integration.

These capabilities are planned and are not implemented yet:

- Windows Task Scheduler integration

## Planned capabilities

- Register an existing automation without modifying its files
- Configure the executable, arguments, and working directory
- Run an automation manually and inspect the result
- Schedule it with Windows Task Scheduler
- Review execution history and captured output
- See the state of every registered automation in one dashboard

## Requirements

- Python 3.11 or newer
- Node.js 22 or newer, for frontend development and for building a wheel

Node.js is not required to run an installed release.

## Development installation

From the repository root:

```powershell
python -m pip install -e ".[dev]"
```

Start the backend:

```powershell
tachibou start
```

The API listens on http://127.0.0.1:8741. In a development checkout the backend does not serve the interface until the frontend has been built and packaged. Start the frontend separately:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The Vite server proxies API requests to the backend.

Use `tachibou start --reload` while changing Python code. `tachibou version` prints the installed version.

Application data is stored outside the repository:

- Windows: `%LOCALAPPDATA%\Tachibou\`
- Linux and macOS: `$XDG_DATA_HOME/tachibou` or `~/.local/share/tachibou`

Set `TACHIBOU_DATA_DIR` to choose another directory. The backend and the future scheduled runner share this location.

## Running an installed build

The intended install for a published release is:

```powershell
pipx install tachibou
tachibou start
```

This repository does not publish packages. To try that layout locally, build a wheel on a machine with Node.js and install it:

```powershell
python -m pip install build
python -m build --wheel
python -m pip install dist\tachibou-*.whl
tachibou start
```

Packaging compiles the frontend and bundles it into the wheel. After installation, open http://127.0.0.1:8741. The backend serves the interface.

Tâchibou binds to `127.0.0.1` by default. It is a local application and is not meant to be exposed on a network.

## Tests and checks

Backend, from the repository root:

```powershell
ruff check .
ruff format --check .
pytest
```

Frontend, from the `frontend` directory:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

## Contributing

Use GitHub Flow. Branch from `main`, keep the branch short-lived, and open a pull request. Write commit messages with Conventional Commits. Continuous integration must pass before merging. Prefer squash merges.

Do not commit secrets or private planning documents.

Development conventions for contributors and coding agents are in `AGENTS.md`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
