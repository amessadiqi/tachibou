"""Persistence models.

Domain tables for automations, schedules, and executions are added with the
features that use them. This foundation keeps a small metadata table so
migrations and the database session have a real schema to exercise.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tachibou.database import Base


class AppMetadata(Base):
    __tablename__ = "app_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
