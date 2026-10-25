"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tachibou.app import create_app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(data_dir: Path) -> Iterator[TestClient]:
    del data_dir
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
