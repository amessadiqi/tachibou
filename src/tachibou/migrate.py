"""Apply Alembic migrations from the installed package."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from tachibou.config import Settings


def migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def upgrade_database(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    command.upgrade(_alembic_config(settings), "head")


def downgrade_database(settings: Settings, revision: str = "base") -> None:
    command.downgrade(_alembic_config(settings), revision)


def _alembic_config(settings: Settings) -> Config:
    config = Config()
    config.set_main_option("script_location", str(migrations_dir()))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config
