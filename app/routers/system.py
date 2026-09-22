import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_db
from app.models import Job
from app.services.llm.prompt import PROMPT_VERSION
from app.services.quota_state import get_daily_quota_pause

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def system_status(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict:
    stmt = (
        select(Job.processing_status, func.count())
        .where(Job.user_id == user_id)
        .group_by(Job.processing_status)
    )
    rows = await db.execute(stmt)
    queue_counts = {status.value: count for status, count in rows.all()}

    # Quota state reflects the shared Gemini API key/worker, so it's
    # global infrastructure state, not scoped to a single user.
    resume_at = get_daily_quota_pause()
    return {
        "queue_counts": queue_counts,
        "quota": {
            "daily_quota_reached": resume_at is not None,
            "resumes_at": resume_at.isoformat() if resume_at else None,
        },
        "llm_model": settings.llm_model,
        "prompt_version": PROMPT_VERSION,
    }
