import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ApplicationStatus,
    EmploymentType,
    ExtractionMethod,
    Importance,
    KeywordCategory,
    Language,
    ProcessingStatus,
    RemotePolicy,
    RoleFamily,
    Seniority,
)

# --- Batch intake (section 5) ---------------------------------------------


class BatchRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)


class BatchResultItem(BaseModel):
    url: str
    result: str  # "accepted" | "duplicate" | "invalid"
    job_id: uuid.UUID | None = None
    reason: str | None = None


# --- Jobs -------------------------------------------------------------------


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str | None
    job_title: str | None
    role_family: RoleFamily | None
    employment_type: EmploymentType | None
    seniority: Seniority | None
    language: Language | None
    location: str | None
    application_status: ApplicationStatus
    processing_status: ProcessingStatus
    processing_error: str | None
    application_deadline: date | None
    created_at: datetime


class JobListResponse(BaseModel):
    items: list[JobListItem]
    total: int


class JobNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    created_at: datetime
    updated_at: datetime


class JobStatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    interview_round: int | None
    changed_at: datetime


class JobKeywordOut(BaseModel):
    keyword_id: uuid.UUID
    canonical_name: str
    category: KeywordCategory
    surface_form: str
    importance: Importance
    evidence_found: bool


class JobDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url: str
    normalized_url: str
    domain: str
    processing_status: ProcessingStatus
    processing_error: str | None
    extraction_method: ExtractionMethod | None
    attempts: int
    raw_text: str | None
    company_name: str | None
    job_title: str | None
    location: str | None
    language: Language | None
    role_family: RoleFamily | None
    seniority: Seniority | None
    employment_type: EmploymentType | None
    remote_policy: RemotePolicy | None
    years_experience_min: int | None
    salary_text: str | None
    application_deadline: date | None
    posted_date: date | None
    summary: str | None
    application_status: ApplicationStatus
    interview_round: int | None
    manually_edited_fields: list[str]
    llm_model: str | None
    prompt_version: str | None
    analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    notes: list[JobNoteOut]
    status_history: list[JobStatusHistoryOut]
    keywords: list[JobKeywordOut] = Field(default_factory=list)


class JobUpdate(BaseModel):
    application_status: ApplicationStatus | None = None
    interview_round: int | None = None
    company_name: str | None = None
    job_title: str | None = None
    location: str | None = None
    role_family: RoleFamily | None = None
    seniority: Seniority | None = None
    employment_type: EmploymentType | None = None
    remote_policy: RemotePolicy | None = None
    application_deadline: date | None = None


class ManualTextRequest(BaseModel):
    text: str


# --- Notes -------------------------------------------------------------------


class NoteCreate(BaseModel):
    body: str


class NoteUpdate(BaseModel):
    body: str


# --- Keywords & dashboard -----------------------------------------------------


class KeywordMergeRequest(BaseModel):
    source_keyword_id: uuid.UUID
    target_keyword_id: uuid.UUID


class KeywordUpdate(BaseModel):
    canonical_name: str | None = None
    category: KeywordCategory | None = None


class SurfaceFormOut(BaseModel):
    text: str
    language: Language | None
    count: int


class KeywordDashboardItem(BaseModel):
    keyword_id: uuid.UUID
    canonical_name: str
    category: KeywordCategory
    job_count: int
    share: float
    must_have_count: int
    nice_to_have_count: int
    surface_forms: list[SurfaceFormOut]


class DashboardKeywordsResponse(BaseModel):
    n_jobs: int
    items: list[KeywordDashboardItem]


class WeekCount(BaseModel):
    week: date
    count: int


class DashboardSummaryResponse(BaseModel):
    by_application_status: dict[str, int]
    by_role_family: dict[str, int]
    by_language: dict[str, int]
    by_employment_type: dict[str, int]
    jobs_per_week: list[WeekCount]
