"""Runtime configuration shared by the server and future runner."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8741


class ConfigError(ValueError):
    """Raised when application configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str
    port: int

    @property
    def database_path(self) -> Path:
        return self.data_dir / "tachibou.db"

    @property
    def database_url(self) -> str:
        return "sqlite:///" + self.database_path.expanduser().resolve().as_posix()


def get_settings() -> Settings:
    return Settings(
        data_dir=_data_dir(),
        host=_host(),
        port=_port(os.environ.get("TACHIBOU_PORT", str(DEFAULT_PORT))),
    )


def validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ConfigError("Port must be between 1 and 65535.")
    return port


def _data_dir() -> Path:
    override = os.environ.get("TACHIBOU_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "Tachibou"
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg_data_home).expanduser() if xdg_data_home else Path.home() / ".local" / "share"
    return base / "tachibou"


def _host() -> str:
    return os.environ.get("TACHIBOU_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST


def _port(value: str) -> int:
    try:
        port = int(value.strip())
    except ValueError as exc:
        raise ConfigError("TACHIBOU_PORT must be an integer.") from exc
    return validate_port(port)
