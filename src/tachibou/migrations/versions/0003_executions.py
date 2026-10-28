"""Create execution history.

Revision ID: 0003_executions
Revises: 0002_automations
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_executions"
down_revision = "0002_automations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("automation_id", sa.String(length=36), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout_path", sa.String(length=1024), nullable=True),
        sa.Column("stderr_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name="fk_execution_automation_id_automation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution"),
    )
    op.create_index(
        "ix_execution_automation_id_started_at",
        "execution",
        ["automation_id", "started_at"],
    )
    op.create_index(
        "uq_execution_one_running",
        "execution",
        ["automation_id"],
        unique=True,
        sqlite_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("uq_execution_one_running", table_name="execution")
    op.drop_index("ix_execution_automation_id_started_at", table_name="execution")
    op.drop_table("execution")
