import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user_id
from app.db import get_db
from app.models import (
    ApplicationStatus,
    EmploymentType,
    ExtractionMethod,
    Job,
    JobKeyword,
    JobNote,
    JobStatusHistory,
    Language,
    ProcessingStatus,
    RoleFamily,
)
from app.schemas import (
    BatchRequest,
    BatchResultItem,
    JobDetail,
    JobKeywordOut,
    JobListItem,
    JobListResponse,
    JobNoteOut,
    JobUpdate,
    ManualTextRequest,
    NoteCreate,
)
from app.services.extraction.quality_gate import passes_quality_gate
from app.services.llm.prompt import PROMPT_VERSION
from app.services.url_normalize import normalize_url

router = APIRouter(prefix="/jobs", tags=["jobs"])

_METADATA_UPDATE_FIELDS = {
    "company_name",
    "job_title",
    "location",
    "role_family",
    "seniority",
    "employment_type",
    "remote_policy",
    "application_deadline",
}

_SORT_COLUMNS = {
    "created_at": Job.created_at,
    "company_name": Job.company_name,
    "job_title": Job.job_title,
    "priority": Job.priority,
    "application_deadline": Job.application_deadline,
}


@router.post("/batch", response_model=list[BatchResultItem])
async def batch_intake(
    body: BatchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[BatchResultItem]:
    results = []
    for raw_url in body.urls:
        normalized = normalize_url(raw_url)
        if normalized is None:
            results.append(
                BatchResultItem(url=raw_url, result="invalid", reason="Not a valid http(s) URL")
            )
            continue
        normalized_url, domain = normalized

        existing = (
            await db.execute(
                select(Job).where(Job.user_id == user_id, Job.normalized_url == normalized_url)
            )
        ).scalar_one_or_none()
        if existing:
            results.append(BatchResultItem(url=raw_url, result="duplicate", job_id=existing.id))
            continue

        job = Job(
            user_id=user_id,
            source_url=raw_url,
            normalized_url=normalized_url,
            domain=domain,
            processing_status=ProcessingStatus.queued,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        results.append(BatchResultItem(url=raw_url, result="accepted", job_id=job.id))

    return results


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    processing_status: ProcessingStatus | None = None,
    application_status: ApplicationStatus | None = None,
    role_family: RoleFamily | None = None,
    employment_type: EmploymentType | None = None,
    language: Language | None = None,
    q: str | None = None,
    sort_by: str = Query(
        "created_at",
        pattern="^(created_at|company_name|job_title|priority|application_deadline)$",
    ),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> JobListResponse:
    filters = [Job.user_id == user_id]
    if processing_status is not None:
        filters.append(Job.processing_status == processing_status)
    if application_status is not None:
        filters.append(Job.application_status == application_status)
    if role_family is not None:
        filters.append(Job.role_family == role_family)
    if employment_type is not None:
        filters.append(Job.employment_type == employment_type)
    if language is not None:
        filters.append(Job.language == language)
    if q:
        like = f"%{q}%"
        filters.append(or_(Job.company_name.ilike(like), Job.job_title.ilike(like)))

    total = (
        await db.execute(select(func.count()).select_from(Job).where(*filters))
    ).scalar_one()

    column = _SORT_COLUMNS[sort_by]
    order = column.desc() if sort_dir == "desc" else column.asc()
    stmt = select(Job).where(*filters).order_by(order).limit(limit).offset(offset)
    jobs = (await db.execute(stmt)).scalars().all()

    return JobListResponse(
        items=[JobListItem.model_validate(job) for job in jobs],
        total=total,
    )


async def _get_job_or_404(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID, *, with_relations: bool = False
) -> Job:
    stmt = select(Job).where(Job.id == job_id, Job.user_id == user_id)
    if with_relations:
        stmt = stmt.options(
            selectinload(Job.notes),
            selectinload(Job.status_history),
            selectinload(Job.job_keywords).selectinload(JobKeyword.keyword),
        )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _to_job_detail(job: Job) -> JobDetail:
    detail = JobDetail.model_validate(job)
    detail.keywords = [
        JobKeywordOut(
            keyword_id=jk.keyword_id,
            canonical_name=jk.keyword.canonical_name,
            category=jk.keyword.category,
            surface_form=jk.surface_form,
            importance=jk.importance,
            evidence_found=jk.evidence_found,
        )
        for jk in job.job_keywords
    ]
    return detail


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetail:
    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    return _to_job_detail(job)


@router.patch("/{job_id}", response_model=JobDetail)
async def update_job(
    job_id: uuid.UUID,
    body: JobUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetail:
    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    updates = body.model_dump(exclude_unset=True)

    if "application_status" in updates or "interview_round" in updates:
        new_status = updates.get("application_status", job.application_status)
        new_round = updates.get("interview_round", job.interview_round)
        if new_status != job.application_status or new_round != job.interview_round:
            db.add(
                JobStatusHistory(
                    job_id=job.id,
                    from_status=job.application_status,
                    to_status=new_status,
                    interview_round=new_round,
                )
            )
        job.application_status = new_status
        job.interview_round = new_round

    if "priority" in updates:
        job.priority = updates["priority"]

    edited = set(job.manually_edited_fields or [])
    for field in _METADATA_UPDATE_FIELDS:
        if field in updates:
            setattr(job, field, updates[field])
            edited.add(field)
    job.manually_edited_fields = sorted(edited)

    await db.commit()
    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    return _to_job_detail(job)


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    job = await _get_job_or_404(db, job_id, user_id)
    await db.delete(job)
    await db.commit()


@router.put("/{job_id}/manual-text", response_model=JobDetail)
async def submit_manual_text(
    job_id: uuid.UUID,
    body: ManualTextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetail:
    job = await _get_job_or_404(db, job_id, user_id)
    if not passes_quality_gate(body.text):
        raise HTTPException(
            status_code=422, detail="Text is too short (minimum 150 words) to analyze."
        )

    job.raw_text = body.text
    job.raw_text_chars = len(body.text)
    job.extraction_method = ExtractionMethod.manual
    job.processing_status = ProcessingStatus.queued
    job.processing_error = None
    await db.commit()

    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    return _to_job_detail(job)


@router.post("/{job_id}/retry", response_model=JobDetail)
async def retry_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetail:
    job = await _get_job_or_404(db, job_id, user_id)
    if job.processing_status not in (ProcessingStatus.failed, ProcessingStatus.needs_manual_text):
        raise HTTPException(
            status_code=409, detail="Only 'failed' or 'needs_manual_text' jobs can be retried."
        )

    job.processing_status = ProcessingStatus.queued
    job.processing_error = None
    job.extraction_method = None
    job.raw_text = None
    job.raw_text_chars = None
    job.attempts = 0
    await db.commit()

    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    return _to_job_detail(job)


@router.post("/{job_id}/reanalyze", response_model=JobDetail)
async def reanalyze_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetail:
    job = await _get_job_or_404(db, job_id, user_id)
    if not job.raw_text:
        raise HTTPException(status_code=409, detail="Job has no extracted text to reanalyze.")

    job.processing_status = ProcessingStatus.queued
    job.processing_error = None
    await db.commit()

    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    return _to_job_detail(job)


@router.post("/{job_id}/analyze", response_model=JobDetail)
async def analyze_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetail:
    job = await _get_job_or_404(db, job_id, user_id)
    if job.processing_status != ProcessingStatus.needs_review:
        raise HTTPException(status_code=409, detail="Job is not awaiting review.")

    job.processing_status = ProcessingStatus.queued
    job.processing_error = None
    await db.commit()

    job = await _get_job_or_404(db, job_id, user_id, with_relations=True)
    return _to_job_detail(job)


@router.post("/reanalyze-outdated")
async def reanalyze_outdated_jobs(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict:
    stmt = select(Job).where(
        Job.user_id == user_id,
        Job.raw_text.isnot(None),
        Job.prompt_version.isnot(None),
        Job.prompt_version != PROMPT_VERSION,
    )
    jobs = (await db.execute(stmt)).scalars().all()
    for job in jobs:
        job.processing_status = ProcessingStatus.queued
        job.processing_error = None
    await db.commit()
    return {"requeued": len(jobs)}


@router.post("/{job_id}/notes", response_model=JobNoteOut, status_code=201)
async def add_note(
    job_id: uuid.UUID,
    body: NoteCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobNote:
    await _get_job_or_404(db, job_id, user_id)
    note = JobNote(job_id=job_id, body=body.body)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note
