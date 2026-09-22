"""add users, scope jobs to a user

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Pre-existing jobs (all from single-user smoke testing, no real user
    # data) have no owner to backfill onto — clear them. Dependent rows
    # (notes, status history, job_keywords) cascade from this delete.
    op.execute("DELETE FROM jobs")

    op.drop_constraint("jobs_normalized_url_key", "jobs", type_="unique")
    op.add_column(
        "jobs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_jobs_user_id", "jobs", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_unique_constraint(
        "uq_user_normalized_url", "jobs", ["user_id", "normalized_url"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_normalized_url", "jobs", type_="unique")
    op.drop_constraint("fk_jobs_user_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "user_id")
    op.create_unique_constraint("jobs_normalized_url_key", "jobs", ["normalized_url"])
    op.drop_table("users")
