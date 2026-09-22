"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-22

"""
import json
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.services.normalize import normalize_key

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


processing_status_enum = postgresql.ENUM(
    "queued",
    "fetching",
    "extracting",
    "analyzing",
    "done",
    "needs_manual_text",
    "quota_wait",
    "failed",
    name="processing_status",
    create_type=False,
)
extraction_method_enum = postgresql.ENUM(
    "json_ld", "ats_api", "readability", "manual", name="extraction_method", create_type=False
)
language_enum = postgresql.ENUM("de", "en", "other", name="language", create_type=False)
role_family_enum = postgresql.ENUM(
    "data_analyst", "data_engineer", "ai_engineer", "other", name="role_family", create_type=False
)
seniority_enum = postgresql.ENUM(
    "intern",
    "working_student",
    "entry",
    "mid",
    "senior",
    "unknown",
    name="seniority",
    create_type=False,
)
employment_type_enum = postgresql.ENUM(
    "full_time",
    "part_time",
    "internship",
    "working_student",
    "trainee",
    "contract",
    "unknown",
    name="employment_type",
    create_type=False,
)
remote_policy_enum = postgresql.ENUM(
    "onsite", "hybrid", "remote", "unknown", name="remote_policy", create_type=False
)
application_status_enum = postgresql.ENUM(
    "saved",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "withdrawn",
    "closed",
    name="application_status",
    create_type=False,
)
keyword_category_enum = postgresql.ENUM(
    "hard_skill",
    "tool",
    "soft_skill",
    "certification",
    "language",
    "domain_knowledge",
    "methodology",
    name="keyword_category",
    create_type=False,
)
importance_enum = postgresql.ENUM(
    "must_have", "nice_to_have", "unclear", name="importance", create_type=False
)

ALL_ENUMS = [
    processing_status_enum,
    extraction_method_enum,
    language_enum,
    role_family_enum,
    seniority_enum,
    employment_type_enum,
    remote_policy_enum,
    application_status_enum,
    keyword_category_enum,
    importance_enum,
]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("normalized_url", sa.Text, nullable=False, unique=True),
        sa.Column("domain", sa.Text, nullable=False),
        sa.Column(
            "processing_status",
            processing_status_enum,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("extraction_method", extraction_method_enum, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("raw_text_chars", sa.Integer, nullable=True),
        sa.Column("json_ld_hints", postgresql.JSONB, nullable=True),
        sa.Column("company_name", sa.Text, nullable=True),
        sa.Column("job_title", sa.Text, nullable=True),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("language", language_enum, nullable=True),
        sa.Column("role_family", role_family_enum, nullable=True),
        sa.Column("seniority", seniority_enum, nullable=True),
        sa.Column("employment_type", employment_type_enum, nullable=True),
        sa.Column("remote_policy", remote_policy_enum, nullable=True),
        sa.Column("years_experience_min", sa.Integer, nullable=True),
        sa.Column("salary_text", sa.Text, nullable=True),
        sa.Column("application_deadline", sa.Date, nullable=True),
        sa.Column("posted_date", sa.Date, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "application_status",
            application_status_enum,
            nullable=False,
            server_default="saved",
        ),
        sa.Column("interview_round", sa.Integer, nullable=True),
        sa.Column("llm_model", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.Text, nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manually_edited_fields", postgresql.JSONB, nullable=True),
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

    op.create_table(
        "job_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
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

    op.create_table(
        "job_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", application_status_enum, nullable=True),
        sa.Column("to_status", application_status_enum, nullable=False),
        sa.Column("interview_round", sa.Integer, nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.Text, nullable=False),
        sa.Column("canonical_key", sa.Text, nullable=False, unique=True),
        sa.Column("category", keyword_category_enum, nullable=False),
    )

    op.create_table(
        "keyword_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "keyword_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("keywords.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_key", sa.Text, nullable=False, unique=True),
    )

    op.create_table(
        "job_keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "keyword_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("keywords.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("surface_form", sa.Text, nullable=False),
        sa.Column("importance", importance_enum, nullable=False),
        sa.Column("evidence_found", sa.Boolean, nullable=False, server_default="false"),
        sa.UniqueConstraint("job_id", "keyword_id", name="uq_job_keyword"),
    )

    _seed_aliases(bind)


def _seed_aliases(bind) -> None:
    seed_path = Path(__file__).resolve().parents[2] / "app" / "data" / "seed_aliases.json"
    entries = json.loads(seed_path.read_text())

    keywords_table = sa.table(
        "keywords",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("canonical_name", sa.Text),
        sa.column("canonical_key", sa.Text),
        sa.column("category", keyword_category_enum),
    )
    aliases_table = sa.table(
        "keyword_aliases",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("keyword_id", postgresql.UUID(as_uuid=True)),
        sa.column("alias_key", sa.Text),
    )

    for entry in entries:
        keyword_id = uuid.uuid4()
        bind.execute(
            keywords_table.insert().values(
                id=keyword_id,
                canonical_name=entry["canonical_name"],
                canonical_key=normalize_key(entry["canonical_name"]),
                category=entry["category"],
            )
        )
        for alias in entry["aliases"]:
            bind.execute(
                aliases_table.insert().values(
                    id=uuid.uuid4(),
                    keyword_id=keyword_id,
                    alias_key=normalize_key(alias),
                )
            )


def downgrade() -> None:
    op.drop_table("job_keywords")
    op.drop_table("keyword_aliases")
    op.drop_table("keywords")
    op.drop_table("job_status_history")
    op.drop_table("job_notes")
    op.drop_table("jobs")
    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.drop(bind, checkfirst=True)
