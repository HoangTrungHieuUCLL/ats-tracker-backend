from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobKeyword, Keyword, KeywordAlias, ProcessingStatus
from app.services.llm.prompt import PROMPT_VERSION
from app.services.llm.schema import JobAnalysis
from app.services.normalize import normalize_for_evidence, normalize_key

_METADATA_FIELDS = [
    "company_name",
    "job_title",
    "location",
    "language",
    "role_family",
    "seniority",
    "employment_type",
    "remote_policy",
    "years_experience_min",
    "salary_text",
    "application_deadline",
    "posted_date",
    "summary",
]


async def apply_analysis(
    session: AsyncSession, job: Job, analysis: JobAnalysis, llm_model: str
) -> None:
    """Write an LLM analysis onto a job (sections 7.4-7.5).

    Metadata fields the user has manually edited are preserved. Keywords are
    resolved against existing keywords/aliases (creating new ones as
    needed) and checked for evidence in the raw job text.
    """
    edited = set(job.manually_edited_fields or [])
    for field in _METADATA_FIELDS:
        if field not in edited:
            setattr(job, field, getattr(analysis, field))

    await session.execute(JobKeyword.__table__.delete().where(JobKeyword.job_id == job.id))

    normalized_raw_text = normalize_for_evidence(job.raw_text or "")
    seen_keyword_ids = set()
    for kw in analysis.keywords:
        keyword = await _resolve_keyword(session, kw.canonical_name, kw.category)
        if keyword.id in seen_keyword_ids:
            continue
        seen_keyword_ids.add(keyword.id)

        evidence_found = normalize_for_evidence(kw.surface_form) in normalized_raw_text
        session.add(
            JobKeyword(
                job_id=job.id,
                keyword_id=keyword.id,
                surface_form=kw.surface_form,
                importance=kw.importance,
                evidence_found=evidence_found,
            )
        )

    job.llm_model = llm_model
    job.prompt_version = PROMPT_VERSION
    job.analyzed_at = datetime.now(UTC)
    job.processing_status = ProcessingStatus.done
    await session.commit()


async def _resolve_keyword(session: AsyncSession, canonical_name: str, category) -> Keyword:
    key = normalize_key(canonical_name)

    alias = (
        await session.execute(select(KeywordAlias).where(KeywordAlias.alias_key == key))
    ).scalar_one_or_none()
    if alias:
        keyword = await session.get(Keyword, alias.keyword_id)
        if keyword:
            return keyword

    keyword = (
        await session.execute(select(Keyword).where(Keyword.canonical_key == key))
    ).scalar_one_or_none()
    if keyword:
        return keyword

    keyword = Keyword(canonical_name=canonical_name, canonical_key=key, category=category)
    session.add(keyword)
    await session.flush()
    return keyword
