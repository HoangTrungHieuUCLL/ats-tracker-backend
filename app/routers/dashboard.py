import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.db import get_db
from app.models import (
    ApplicationStatus,
    EmploymentType,
    Importance,
    Job,
    JobKeyword,
    Keyword,
    KeywordCategory,
    Language,
    ProcessingStatus,
    RoleFamily,
    Seniority,
)
from app.schemas import (
    DashboardKeywordsResponse,
    DashboardSummaryResponse,
    KeywordDashboardItem,
    SurfaceFormOut,
    WeekCount,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _job_filters(
    user_id: uuid.UUID,
    role_family: RoleFamily | None,
    language: Language | None,
    seniority: Seniority | None,
    employment_type: EmploymentType | None,
    application_status: ApplicationStatus | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list:
    filters = [Job.user_id == user_id, Job.processing_status == ProcessingStatus.done]
    if role_family is not None:
        filters.append(Job.role_family == role_family)
    if language is not None:
        filters.append(Job.language == language)
    if seniority is not None:
        filters.append(Job.seniority == seniority)
    if employment_type is not None:
        filters.append(Job.employment_type == employment_type)
    if application_status is not None:
        filters.append(Job.application_status == application_status)
    if date_from is not None:
        filters.append(Job.created_at >= date_from)
    if date_to is not None:
        filters.append(Job.created_at <= date_to)
    return filters


@router.get("/keywords", response_model=DashboardKeywordsResponse)
async def dashboard_keywords(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    role_family: RoleFamily | None = None,
    language: Language | None = None,
    seniority: Seniority | None = None,
    employment_type: EmploymentType | None = None,
    application_status: ApplicationStatus | None = None,
    importance: Importance | None = None,
    category: KeywordCategory | None = None,
    include_unverified: bool = False,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = Query(25, ge=1, le=200),
) -> DashboardKeywordsResponse:
    job_filters = _job_filters(
        user_id,
        role_family,
        language,
        seniority,
        employment_type,
        application_status,
        date_from,
        date_to,
    )

    n_jobs = (
        await db.execute(select(func.count()).select_from(Job).where(*job_filters))
    ).scalar_one()

    kw_filters = list(job_filters)
    if importance is not None:
        kw_filters.append(JobKeyword.importance == importance)
    if category is not None:
        kw_filters.append(Keyword.category == category)
    if not include_unverified:
        kw_filters.append(JobKeyword.evidence_found.is_(True))

    agg_stmt = (
        select(
            Keyword.id,
            Keyword.canonical_name,
            Keyword.category,
            func.count(JobKeyword.id).label("job_count"),
            func.sum(case((JobKeyword.importance == Importance.must_have, 1), else_=0)).label(
                "must_have_count"
            ),
            func.sum(case((JobKeyword.importance == Importance.nice_to_have, 1), else_=0)).label(
                "nice_to_have_count"
            ),
        )
        .join(JobKeyword, JobKeyword.keyword_id == Keyword.id)
        .join(Job, Job.id == JobKeyword.job_id)
        .where(*kw_filters)
        .group_by(Keyword.id, Keyword.canonical_name, Keyword.category)
        .order_by(func.count(JobKeyword.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(agg_stmt)).all()

    items = []
    for keyword_id, canonical_name, category_, job_count, must_have, nice_to_have in rows:
        sf_stmt = (
            select(JobKeyword.surface_form, Job.language, func.count())
            .join(Job, Job.id == JobKeyword.job_id)
            .where(*kw_filters, JobKeyword.keyword_id == keyword_id)
            .group_by(JobKeyword.surface_form, Job.language)
            .order_by(func.count().desc())
        )
        surface_rows = (await db.execute(sf_stmt)).all()
        items.append(
            KeywordDashboardItem(
                keyword_id=keyword_id,
                canonical_name=canonical_name,
                category=category_,
                job_count=job_count,
                share=(job_count / n_jobs) if n_jobs else 0.0,
                must_have_count=must_have,
                nice_to_have_count=nice_to_have,
                surface_forms=[
                    SurfaceFormOut(text=text, language=lang, count=count)
                    for text, lang, count in surface_rows
                ],
            )
        )

    return DashboardKeywordsResponse(n_jobs=n_jobs, items=items)


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DashboardSummaryResponse:
    async def _counts(column) -> dict[str, int]:
        rows = (
            await db.execute(
                select(column, func.count()).where(Job.user_id == user_id).group_by(column)
            )
        ).all()
        return {(value.value if value is not None else "unknown"): count for value, count in rows}

    by_application_status = await _counts(Job.application_status)
    by_role_family = await _counts(Job.role_family)
    by_language = await _counts(Job.language)
    by_employment_type = await _counts(Job.employment_type)

    week = func.date_trunc("week", Job.created_at)
    week_rows = (
        await db.execute(
            select(week, func.count())
            .where(Job.user_id == user_id)
            .group_by(week)
            .order_by(week)
        )
    ).all()

    return DashboardSummaryResponse(
        by_application_status=by_application_status,
        by_role_family=by_role_family,
        by_language=by_language,
        by_employment_type=by_employment_type,
        jobs_per_week=[WeekCount(week=w.date(), count=c) for w, c in week_rows],
    )
