"""Configuration resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from tachibou import config
from tachibou.config import ConfigError, get_settings


def test_override_selects_the_data_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "custom"
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(target))
    assert get_settings().data_dir == target


def test_default_linux_data_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TACHIBOU_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    assert get_settings().data_dir == Path.home() / ".local" / "share" / "tachibou"


def test_xdg_data_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TACHIBOU_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(config.sys, "platform", "linux")
    assert get_settings().data_dir == tmp_path / "tachibou"


def test_windows_local_app_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TACHIBOU_DATA_DIR", raising=False)
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\dev\AppData\Local")
    data_dir = get_settings().data_dir
    assert data_dir.name == "Tachibou"
    assert data_dir.parent == Path(r"C:\Users\dev\AppData\Local")


def test_database_url_points_at_the_data_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(tmp_path))
    url = get_settings().database_url
    assert url.startswith("sqlite:///")
    assert url.endswith("/tachibou.db")
    assert tmp_path.as_posix() in url


def test_network_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TACHIBOU_HOST", raising=False)
    monkeypatch.delenv("TACHIBOU_PORT", raising=False)
    settings = get_settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8741


def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TACHIBOU_PORT", "nope")
    with pytest.raises(ConfigError, match="TACHIBOU_PORT"):
        get_settings()
