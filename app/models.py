import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from app.db import Base


class ProcessingStatus(str, enum.Enum):
    queued = "queued"
    fetching = "fetching"
    extracting = "extracting"
    analyzing = "analyzing"
    done = "done"
    needs_review = "needs_review"
    needs_manual_text = "needs_manual_text"
    quota_wait = "quota_wait"
    failed = "failed"


class ExtractionMethod(str, enum.Enum):
    json_ld = "json_ld"
    ats_api = "ats_api"
    readability = "readability"
    manual = "manual"


class Language(str, enum.Enum):
    de = "de"
    en = "en"
    other = "other"


class RoleFamily(str, enum.Enum):
    data_analyst = "data_analyst"
    data_engineer = "data_engineer"
    ai_engineer = "ai_engineer"
    other = "other"


class Seniority(str, enum.Enum):
    intern = "intern"
    working_student = "working_student"
    entry = "entry"
    mid = "mid"
    senior = "senior"
    unknown = "unknown"


class EmploymentType(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    internship = "internship"
    working_student = "working_student"
    trainee = "trainee"
    contract = "contract"
    unknown = "unknown"


class RemotePolicy(str, enum.Enum):
    onsite = "onsite"
    hybrid = "hybrid"
    remote = "remote"
    unknown = "unknown"


class ApplicationStatus(str, enum.Enum):
    saved = "saved"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    closed = "closed"


class KeywordCategory(str, enum.Enum):
    hard_skill = "hard_skill"
    tool = "tool"
    soft_skill = "soft_skill"
    certification = "certification"
    language = "language"
    domain_knowledge = "domain_knowledge"
    methodology = "methodology"


class Importance(str, enum.Enum):
    must_have = "must_have"
    nice_to_have = "nice_to_have"
    unclear = "unclear"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _enum(python_enum: type[enum.Enum], name: str, nullable: bool = False, default=None):
    sa_enum = SAEnum(
        python_enum, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e]
    )
    return mapped_column(sa_enum, nullable=nullable, default=default)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)

    jobs: Mapped[list["Job"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("user_id", "normalized_url", name="uq_user_normalized_url"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    source_url: Mapped[str] = mapped_column(Text)
    normalized_url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(Text)

    processing_status: Mapped[ProcessingStatus] = _enum(
        ProcessingStatus, "processing_status", default=ProcessingStatus.queued
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[ExtractionMethod | None] = _enum(
        ExtractionMethod, "extraction_method", nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    json_ld_hints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[Language | None] = _enum(Language, "language", nullable=True)
    role_family: Mapped[RoleFamily | None] = _enum(RoleFamily, "role_family", nullable=True)
    seniority: Mapped[Seniority | None] = _enum(Seniority, "seniority", nullable=True)
    employment_type: Mapped[EmploymentType | None] = _enum(
        EmploymentType, "employment_type", nullable=True
    )
    remote_policy: Mapped[RemotePolicy | None] = _enum(RemotePolicy, "remote_policy", nullable=True)
    years_experience_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    application_status: Mapped[ApplicationStatus] = _enum(
        ApplicationStatus, "application_status", default=ApplicationStatus.saved
    )
    interview_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    manually_edited_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    user: Mapped["User"] = relationship(back_populates="jobs")
    notes: Mapped[list["JobNote"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobNote.created_at.desc()"
    )
    status_history: Mapped[list["JobStatusHistory"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobStatusHistory.changed_at"
    )
    job_keywords: Mapped[list["JobKeyword"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobNote(Base):
    __tablename__ = "job_notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    job: Mapped["Job"] = relationship(back_populates="notes")


class JobStatusHistory(Base):
    __tablename__ = "job_status_history"

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    from_status: Mapped[ApplicationStatus | None] = _enum(
        ApplicationStatus, "application_status", nullable=True
    )
    to_status: Mapped[ApplicationStatus] = _enum(ApplicationStatus, "application_status")
    interview_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="status_history")


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[uuid.UUID] = _uuid_pk()
    canonical_name: Mapped[str] = mapped_column(Text)
    canonical_key: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[KeywordCategory] = _enum(KeywordCategory, "keyword_category")

    aliases: Mapped[list["KeywordAlias"]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )
    job_keywords: Mapped[list["JobKeyword"]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )


class KeywordAlias(Base):
    __tablename__ = "keyword_aliases"

    id: Mapped[uuid.UUID] = _uuid_pk()
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE")
    )
    alias_key: Mapped[str] = mapped_column(Text, unique=True)

    keyword: Mapped["Keyword"] = relationship(back_populates="aliases")


class JobKeyword(Base):
    __tablename__ = "job_keywords"
    __table_args__ = (UniqueConstraint("job_id", "keyword_id", name="uq_job_keyword"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE")
    )
    surface_form: Mapped[str] = mapped_column(Text)
    importance: Mapped[Importance] = _enum(Importance, "importance")
    evidence_found: Mapped[bool] = mapped_column(Boolean, default=False)

    job: Mapped["Job"] = relationship(back_populates="job_keywords")
    keyword: Mapped["Keyword"] = relationship(back_populates="job_keywords")
