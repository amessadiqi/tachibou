"""Persistence models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tachibou.database import Base


class AppMetadata(Base):
    __tablename__ = "app_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)


class Automation(Base):
    __tablename__ = "automation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executable: Mapped[str] = mapped_column(String(1024), nullable=False)
    arguments: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    working_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    entry_point: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    file_references: Mapped[list[FileReference]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    executions: Mapped[list[Execution]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FileReference(Base):
    __tablename__ = "file_reference"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    automation_id: Mapped[str] = mapped_column(
        ForeignKey("automation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    automation: Mapped[Automation] = relationship(back_populates="file_references")


class Execution(Base):
    __tablename__ = "execution"
    __table_args__ = (
        Index("ix_execution_automation_id_started_at", "automation_id", "started_at"),
        Index(
            "uq_execution_one_running",
            "automation_id",
            unique=True,
            sqlite_where=text("status = 'running'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    automation_id: Mapped[str] = mapped_column(
        ForeignKey("automation.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Kept for the runner contract. The schedule table arrives with scheduling.
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    stderr_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    automation: Mapped[Automation] = relationship(back_populates="executions")
