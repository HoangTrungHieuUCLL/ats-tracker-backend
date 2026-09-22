import itertools

from app.db import async_session_maker
from app.models import Job, ProcessingStatus

_url_counter = itertools.count()


async def _insert_job(status: ProcessingStatus) -> None:
    async with async_session_maker() as session:
        n = next(_url_counter)
        session.add(
            Job(
                source_url="https://example.com/jobs/1",
                normalized_url=f"https://example.com/jobs/{status.value}-{n}",
                domain="example.com",
                processing_status=status,
            )
        )
        await session.commit()


async def test_system_status_reports_queue_counts_and_quota(client, auth_headers, clean_jobs_table):
    await _insert_job(ProcessingStatus.queued)
    await _insert_job(ProcessingStatus.done)
    await _insert_job(ProcessingStatus.done)

    response = await client.get("/system/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["queue_counts"]["queued"] == 1
    assert body["queue_counts"]["done"] == 2
    assert body["quota"]["daily_quota_reached"] is False
    assert body["quota"]["resumes_at"] is None
    assert body["prompt_version"] == "v1"


async def test_system_status_requires_auth(client, clean_jobs_table):
    response = await client.get("/system/status")
    assert response.status_code == 401
