from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.db import async_session_maker
from app.models import ExtractionMethod, Job, ProcessingStatus
from app.services.llm.schema import JobAnalysis
from app.worker import claim_next_job, process_job, reset_stuck_jobs
from tests.factories import TEST_USER_ID

LONG_DESCRIPTION = "<p>" + " ".join(["Requirement"] * 200) + "</p>"

JOB_POSTING_HTML = f"""<html><head>
<script type="application/ld+json">
{{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "Data Analyst",
  "description": "{LONG_DESCRIPTION}",
  "hiringOrganization": {{"@type": "Organization", "name": "Acme GmbH"}}
}}
</script>
</head><body></body></html>"""

SHORT_HTML = "<html><body><p>Too short to pass the quality gate.</p></body></html>"


async def _insert_job(url: str = "https://example.com/jobs/1") -> Job:
    async with async_session_maker() as session:
        job = Job(
            user_id=TEST_USER_ID,
            source_url=url,
            normalized_url=url,
            domain="example.com",
            processing_status=ProcessingStatus.queued,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def _reload(job_id) -> Job:
    async with async_session_maker() as session:
        return await session.get(Job, job_id)


class _FakeLLMClient:
    model = "fake-model"

    async def analyze(self, job_text, hints):
        return JobAnalysis(job_title="Data Analyst", keywords=[])


@pytest.mark.asyncio
@respx.mock
async def test_process_job_success_via_json_ld_stops_for_review(clean_jobs_table, monkeypatch):
    def _fail_if_called():
        raise AssertionError("LLM must not be called before review approval")

    monkeypatch.setattr("app.worker._get_llm_client", _fail_if_called)
    job = await _insert_job()
    respx.get(job.source_url).mock(return_value=httpx.Response(200, text=JOB_POSTING_HTML))

    await process_job(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.needs_review
    assert updated.extraction_method == ExtractionMethod.json_ld
    assert "Requirement" in updated.raw_text
    assert updated.job_title is None


@pytest.mark.asyncio
@respx.mock
async def test_process_job_skips_refetch_and_analyzes_after_review_approval(
    clean_jobs_table, monkeypatch
):
    monkeypatch.setattr("app.worker._get_llm_client", lambda: _FakeLLMClient())
    job = await _insert_job()
    async with async_session_maker() as session:
        db_job = await session.get(Job, job.id)
        db_job.processing_status = ProcessingStatus.queued
        db_job.extraction_method = ExtractionMethod.json_ld
        db_job.raw_text = "Already extracted text, approved for analysis."
        await session.commit()

    await process_job(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.done
    assert updated.job_title == "Data Analyst"


@pytest.mark.asyncio
@respx.mock
async def test_process_job_blocked_goes_to_needs_manual_text(clean_jobs_table):
    job = await _insert_job()
    respx.get(job.source_url).mock(return_value=httpx.Response(403))

    await process_job(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.needs_manual_text
    assert "403" in updated.processing_error


@pytest.mark.asyncio
@respx.mock
async def test_process_job_transient_failure_ends_in_failed(clean_jobs_table, monkeypatch):
    monkeypatch.setattr("app.worker.RETRY_BACKOFF_SECONDS", [0, 0, 0])
    job = await _insert_job()
    respx.get(job.source_url).mock(return_value=httpx.Response(500))

    await process_job(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.failed
    assert updated.attempts == 3


@pytest.mark.asyncio
@respx.mock
async def test_process_job_all_steps_fail_quality_gate(clean_jobs_table):
    job = await _insert_job()
    respx.get(job.source_url).mock(return_value=httpx.Response(200, text=SHORT_HTML))

    await process_job(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.needs_manual_text


@pytest.mark.asyncio
async def test_claim_next_job_picks_oldest_queued(clean_jobs_table):
    older = await _insert_job("https://example.com/jobs/older")
    async with async_session_maker() as session:
        db_job = await session.get(Job, older.id)
        db_job.created_at = datetime.now(UTC) - timedelta(minutes=5)
        await session.commit()
    await _insert_job("https://example.com/jobs/newer")

    claimed_id = await claim_next_job()

    assert claimed_id == older.id
    updated = await _reload(older.id)
    assert updated.processing_status == ProcessingStatus.fetching


@pytest.mark.asyncio
async def test_claim_next_job_returns_none_when_nothing_queued(clean_jobs_table):
    assert await claim_next_job() is None


@pytest.mark.asyncio
async def test_reset_stuck_jobs_requeues_old_in_progress_jobs(clean_jobs_table):
    job = await _insert_job()
    async with async_session_maker() as session:
        db_job = await session.get(Job, job.id)
        db_job.processing_status = ProcessingStatus.extracting
        db_job.updated_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.commit()

    await reset_stuck_jobs()

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.queued


@pytest.mark.asyncio
async def test_reset_stuck_jobs_leaves_recent_in_progress_jobs(clean_jobs_table):
    job = await _insert_job()
    async with async_session_maker() as session:
        db_job = await session.get(Job, job.id)
        db_job.processing_status = ProcessingStatus.extracting
        await session.commit()

    await reset_stuck_jobs()

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.extracting


@pytest.mark.asyncio
async def test_batch_intake_accepts_dedupes_and_validates(client, auth_headers, clean_jobs_table):
    response = await client.post(
        "/jobs/batch",
        json={
            "urls": [
                "https://example.com/jobs/1?utm_source=x",
                "https://example.com/jobs/1",
                "not-a-url",
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    results = response.json()
    assert results[0]["result"] == "accepted"
    assert results[1]["result"] == "duplicate"
    assert results[1]["job_id"] == results[0]["job_id"]
    assert results[2]["result"] == "invalid"


async def test_batch_intake_enforces_max_10_urls(client, auth_headers, clean_jobs_table):
    urls = [f"https://example.com/jobs/{i}" for i in range(11)]
    response = await client.post("/jobs/batch", json={"urls": urls}, headers=auth_headers)
    assert response.status_code == 422


async def test_batch_intake_requires_auth(client, clean_jobs_table):
    response = await client.post("/jobs/batch", json={"urls": ["https://example.com/jobs/1"]})
    assert response.status_code == 401
