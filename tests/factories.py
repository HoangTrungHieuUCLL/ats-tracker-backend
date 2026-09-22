import itertools
import uuid

from app.db import async_session_maker
from app.models import Job, JobKeyword, Keyword, ProcessingStatus

_counter = itertools.count()


async def insert_job(**overrides) -> Job:
    n = next(_counter)
    defaults = dict(
        source_url=f"https://example.com/jobs/{n}",
        normalized_url=f"https://example.com/jobs/{n}",
        domain="example.com",
        processing_status=ProcessingStatus.queued,
        manually_edited_fields=[],
    )
    defaults.update(overrides)
    async with async_session_maker() as session:
        job = Job(**defaults)
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def insert_keyword(**overrides) -> Keyword:
    n = next(_counter)
    defaults = dict(canonical_name=f"Skill {n}", canonical_key=f"skill {n}", category="tool")
    defaults.update(overrides)
    async with async_session_maker() as session:
        keyword = Keyword(**defaults)
        session.add(keyword)
        await session.commit()
        await session.refresh(keyword)
        return keyword


async def insert_job_keyword(job_id: uuid.UUID, keyword_id: uuid.UUID, **overrides) -> JobKeyword:
    defaults = dict(surface_form="Skill", importance="must_have", evidence_found=True)
    defaults.update(overrides)
    async with async_session_maker() as session:
        jk = JobKeyword(job_id=job_id, keyword_id=keyword_id, **defaults)
        session.add(jk)
        await session.commit()
        await session.refresh(jk)
        return jk
