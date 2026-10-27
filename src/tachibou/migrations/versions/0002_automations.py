"""Create automation registrations and file references.

Revision ID: 0002_automations
Revises: 0001_initial
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_automations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=200), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("executable", sa.String(length=1024), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("working_directory", sa.String(length=1024), nullable=False),
        sa.Column("entry_point", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_automation"),
    )
    op.create_index("ix_automation_name", "automation", ["name"])
    op.create_table(
        "file_reference",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("automation_id", sa.String(length=36), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name="fk_file_reference_automation_id_automation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_reference"),
    )
    op.create_index("ix_file_reference_automation_id", "file_reference", ["automation_id"])


def downgrade() -> None:
    op.drop_index("ix_file_reference_automation_id", table_name="file_reference")
    op.drop_table("file_reference")
    op.drop_index("ix_automation_name", table_name="automation")
    op.drop_table("automation")
