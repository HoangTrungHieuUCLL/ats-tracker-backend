import csv
import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.db import get_db
from app.models import Job

router = APIRouter(tags=["export"])

_COLUMNS = [
    "id",
    "company_name",
    "job_title",
    "role_family",
    "seniority",
    "employment_type",
    "remote_policy",
    "language",
    "location",
    "application_status",
    "application_deadline",
    "source_url",
    "created_at",
]


@router.get("/export/jobs.csv")
async def export_jobs_csv(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> StreamingResponse:
    stmt = select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc())
    jobs = (await db.execute(stmt)).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_COLUMNS)
    for job in jobs:
        writer.writerow([_csv_value(getattr(job, col)) for col in _COLUMNS])
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"},
    )


def _csv_value(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):  # enum
        return value.value
    return str(value)
