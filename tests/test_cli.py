"""Command line interface."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tachibou import __version__
from tachibou.cli import main


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_module_entrypoint() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tachibou", "version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == __version__


def test_start_uses_configured_bind(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}

    def fake_run(target: object, **kwargs: object) -> None:
        captured["target"] = target
        captured["kwargs"] = kwargs

    monkeypatch.setattr("tachibou.cli.uvicorn.run", fake_run)
    monkeypatch.setenv("TACHIBOU_HOST", "127.0.0.1")
    monkeypatch.setenv("TACHIBOU_PORT", "9001")

    assert main(["start"]) == 0
    output = capsys.readouterr()
    assert captured["kwargs"] == {"factory": True, "host": "127.0.0.1", "port": 9001}
    assert "http://127.0.0.1:9001" in output.out
    assert output.err == ""


def test_reload_uses_the_import_string(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(target: object, **kwargs: object) -> None:
        captured["target"] = target
        captured["kwargs"] = kwargs

    monkeypatch.setattr("tachibou.cli.uvicorn.run", fake_run)
    assert main(["start", "--reload", "--host", "localhost", "--port", "9002"]) == 0
    assert captured["target"] == "tachibou.app:create_app"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["reload"] is True
    assert kwargs["port"] == 9002


def test_non_loopback_host_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("tachibou.cli.uvicorn.run", lambda *args, **kwargs: None)
    assert main(["start", "--host", "0.0.0.0"]) == 0
    assert "unsupported" in capsys.readouterr().err.lower()


def test_invalid_port_returns_an_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("tachibou.cli.uvicorn.run", lambda *args, **kwargs: None)
    assert main(["start", "--port", "70000"]) == 2
    assert "Port" in capsys.readouterr().err


def test_invalid_environment_port_returns_an_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TACHIBOU_PORT", "abc")
    assert main(["start"]) == 2
    assert "TACHIBOU_PORT" in capsys.readouterr().err


def test_missing_command_exits() -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
