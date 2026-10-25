"""Bundle the compiled frontend into the Python wheel."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Compile the React app and include it as package data."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # Editable installs use the wheel builder with version "editable".
        # Development uses the Vite server, so do not require Node.js here.
        if version == "editable" or self.target_name != "wheel":
            return

        root = Path(self.root)
        frontend = root / "frontend"
        if not (frontend / "package.json").is_file():
            raise RuntimeError(f"Frontend project not found at {frontend}")

        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "Node.js and npm are required to build the tachibou wheel. "
                "They are not required to run an installed release."
            )

        _run_npm(npm, ["ci", "--no-fund", "--no-audit"], frontend)
        _run_npm(npm, ["run", "build"], frontend)

        index = frontend / "dist" / "index.html"
        if not index.is_file():
            raise RuntimeError("Frontend build did not produce dist/index.html")

        included = build_data.setdefault("force_include", {})
        included["frontend/dist"] = "tachibou/static"
        included["src/tachibou/migrations/script.py.mako"] = "tachibou/migrations/script.py.mako"


def _run_npm(npm: str, args: list[str], cwd: Path) -> None:
    completed = subprocess.run([npm, *args], cwd=cwd, check=False)
    if completed.returncode != 0:
        command = " ".join(args)
        raise RuntimeError(f"`npm {command}` failed with exit code {completed.returncode}")
