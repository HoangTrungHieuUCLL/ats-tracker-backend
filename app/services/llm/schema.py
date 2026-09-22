from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models import (
    EmploymentType,
    Importance,
    KeywordCategory,
    Language,
    RemotePolicy,
    RoleFamily,
    Seniority,
)


class ExtractedKeyword(BaseModel):
    canonical_name: str
    surface_form: str
    category: KeywordCategory
    importance: Importance


class JobAnalysis(BaseModel):
    company_name: str | None = None
    job_title: str | None = None
    location: str | None = None
    language: Language = Language.other
    role_family: RoleFamily = RoleFamily.other
    seniority: Seniority = Seniority.unknown
    employment_type: EmploymentType = EmploymentType.unknown
    remote_policy: RemotePolicy = RemotePolicy.unknown
    years_experience_min: int | None = None
    salary_text: str | None = None
    application_deadline: date | None = None
    posted_date: date | None = None
    summary: str | None = None
    # Gemini's structured-output API rejects a `maxItems` constraint on array
    # fields (400 INVALID_ARGUMENT), so the "at most 40" cap lives in the
    # prompt (app/prompts/extract_v1.md) instead of a Field constraint here.
    keywords: list[ExtractedKeyword] = Field(default_factory=list)

    @field_validator("keywords")
    @classmethod
    def _cap_at_40(cls, value: list[ExtractedKeyword]) -> list[ExtractedKeyword]:
        return value[:40]
