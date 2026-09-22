from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.db import get_db
from app.models import Job, ProcessingStatus
from app.schemas import BatchRequest, BatchResultItem
from app.services.url_normalize import normalize_url

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_auth)])


@router.post("/batch", response_model=list[BatchResultItem])
async def batch_intake(
    body: BatchRequest, db: AsyncSession = Depends(get_db)
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
            await db.execute(select(Job).where(Job.normalized_url == normalized_url))
        ).scalar_one_or_none()
        if existing:
            results.append(BatchResultItem(url=raw_url, result="duplicate", job_id=existing.id))
            continue

        job = Job(
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
