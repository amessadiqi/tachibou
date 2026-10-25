"""Create the application metadata table.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.String(length=1024), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_app_metadata"),
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
