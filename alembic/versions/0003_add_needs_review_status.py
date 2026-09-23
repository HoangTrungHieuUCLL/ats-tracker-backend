"""add needs_review processing status

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE processing_status ADD VALUE 'needs_review' BEFORE 'needs_manual_text'")


def downgrade() -> None:
    # ponytail: Postgres can't drop enum values; downgrade is a no-op.
    pass
