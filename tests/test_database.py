"""SQLite migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from tachibou.config import get_settings
from tachibou.database import create_db_engine
from tachibou.migrate import downgrade_database, upgrade_database
from tachibou.models import AppMetadata


def test_upgrade_creates_metadata_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    settings = get_settings()

    upgrade_database(settings)
    upgrade_database(settings)

    engine = create_db_engine(settings)
    try:
        assert settings.database_path.is_file()
        assert "app_metadata" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        assert foreign_keys == 1
        assert str(journal_mode).lower() == "wal"
        with Session(engine) as session:
            session.add(AppMetadata(key="installation", value="foundation"))
            session.commit()
            stored = session.get(AppMetadata, "installation")
            assert stored is not None
            assert stored.value == "foundation"
    finally:
        engine.dispose()


def test_downgrade_removes_the_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACHIBOU_DATA_DIR", str(tmp_path))
    settings = get_settings()
    upgrade_database(settings)
    downgrade_database(settings)

    engine = create_db_engine(settings)
    try:
        assert "app_metadata" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    upgrade_database(settings)
    engine = create_db_engine(settings)
    try:
        assert "app_metadata" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
