import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.db import get_db
from app.models import Job, JobKeyword, Keyword, KeywordAlias
from app.schemas import JobListItem, KeywordMergeRequest, KeywordUpdate
from app.services.normalize import normalize_key

router = APIRouter(
    prefix="/keywords", tags=["keywords"], dependencies=[Depends(get_current_user_id)]
)


async def _get_keyword_or_404(db: AsyncSession, keyword_id: uuid.UUID) -> Keyword:
    keyword = await db.get(Keyword, keyword_id)
    if keyword is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return keyword


@router.get("/{keyword_id}/jobs", response_model=list[JobListItem])
async def jobs_for_keyword(
    keyword_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    stmt = (
        select(Job)
        .join(JobKeyword, JobKeyword.job_id == Job.id)
        .where(JobKeyword.keyword_id == keyword_id, Job.user_id == user_id)
        .order_by(Job.created_at.desc())
    )
    jobs = (await db.execute(stmt)).scalars().all()
    return [JobListItem.model_validate(job) for job in jobs]


@router.patch("/{keyword_id}")
async def update_keyword(
    keyword_id: uuid.UUID, body: KeywordUpdate, db: AsyncSession = Depends(get_db)
) -> dict:
    keyword = await _get_keyword_or_404(db, keyword_id)

    if body.canonical_name is not None:
        new_key = normalize_key(body.canonical_name)
        if new_key != keyword.canonical_key:
            clash = (
                await db.execute(select(Keyword).where(Keyword.canonical_key == new_key))
            ).scalar_one_or_none()
            if clash is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Another keyword already has this canonical name.",
                )
        keyword.canonical_name = body.canonical_name
        keyword.canonical_key = new_key

    if body.category is not None:
        keyword.category = body.category

    await db.commit()
    await db.refresh(keyword)
    return {
        "id": str(keyword.id),
        "canonical_name": keyword.canonical_name,
        "category": keyword.category.value,
    }


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(keyword_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    keyword = await _get_keyword_or_404(db, keyword_id)
    await db.delete(keyword)
    await db.commit()


@router.post("/merge")
async def merge_keywords(body: KeywordMergeRequest, db: AsyncSession = Depends(get_db)) -> dict:
    if body.source_keyword_id == body.target_keyword_id:
        raise HTTPException(status_code=400, detail="source and target must differ")

    source = await _get_keyword_or_404(db, body.source_keyword_id)
    target = await _get_keyword_or_404(db, body.target_keyword_id)

    target_job_ids = set(
        (
            await db.execute(
                select(JobKeyword.job_id).where(JobKeyword.keyword_id == target.id)
            )
        ).scalars()
    )

    source_job_keywords = (
        await db.execute(select(JobKeyword).where(JobKeyword.keyword_id == source.id))
    ).scalars().all()

    for jk in source_job_keywords:
        if jk.job_id in target_job_ids:
            # Job already has the target keyword; drop the source row to
            # avoid violating the (job_id, keyword_id) unique constraint.
            await db.delete(jk)
        else:
            jk.keyword_id = target.id

    db.add(KeywordAlias(keyword_id=target.id, alias_key=source.canonical_key))

    existing_aliases = (
        await db.execute(select(KeywordAlias).where(KeywordAlias.keyword_id == source.id))
    ).scalars().all()
    for alias in existing_aliases:
        alias.keyword_id = target.id

    await db.delete(source)
    await db.commit()

    return {"merged_into": str(target.id)}
