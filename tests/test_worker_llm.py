import pytest

from app.db import async_session_maker
from app.models import Job, ProcessingStatus
from app.services import quota_state
from app.services.llm.base import LLMInvalidResponseError, LLMTransientError, QuotaExceeded
from app.services.llm.schema import JobAnalysis
from app.worker import _run_llm_analysis
from tests.factories import TEST_USER_ID


class FakeClient:
    def __init__(self, side_effects):
        self.side_effects = list(side_effects)
        self.calls = 0
        self.model = "fake-model"

    async def analyze(self, job_text, hints):
        self.calls += 1
        effect = self.side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


async def _insert_job() -> Job:
    async with async_session_maker() as session:
        job = Job(
            user_id=TEST_USER_ID,
            source_url="https://example.com/jobs/1",
            normalized_url="https://example.com/jobs/1",
            domain="example.com",
            processing_status=ProcessingStatus.analyzing,
            raw_text="Some extracted job text.",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def _reload(job_id) -> Job:
    async with async_session_maker() as session:
        return await session.get(Job, job_id)


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr("app.worker.LLM_PER_MINUTE_BACKOFF_SECONDS", [0, 0, 0])
    monkeypatch.setattr("app.worker.RETRY_BACKOFF_SECONDS", [0, 0, 0])
    import app.worker as worker_module

    monkeypatch.setattr(worker_module._llm_limiter, "min_seconds", 0)


def _patch_client(monkeypatch, client):
    monkeypatch.setattr("app.worker._get_llm_client", lambda: client)


async def test_success_marks_job_done(clean_jobs_table, monkeypatch):
    job = await _insert_job()
    client = FakeClient([JobAnalysis(job_title="Data Analyst", keywords=[])])
    _patch_client(monkeypatch, client)

    await _run_llm_analysis(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.done
    assert updated.job_title == "Data Analyst"
    assert updated.llm_model == "fake-model"


async def test_daily_quota_exceeded_sets_quota_wait(clean_jobs_table, monkeypatch):
    job = await _insert_job()
    client = FakeClient([QuotaExceeded(is_daily=True, message="daily")])
    _patch_client(monkeypatch, client)

    await _run_llm_analysis(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.quota_wait
    assert updated.next_attempt_at is not None
    assert client.calls == 1


async def test_ambiguous_per_minute_exhausted_falls_back_to_daily(clean_jobs_table, monkeypatch):
    job = await _insert_job()
    client = FakeClient([QuotaExceeded(is_daily=False, message="unclear")] * 3)
    _patch_client(monkeypatch, client)

    await _run_llm_analysis(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.quota_wait
    assert client.calls == 3


async def test_transient_errors_exhaust_to_failed(clean_jobs_table, monkeypatch):
    job = await _insert_job()
    client = FakeClient([LLMTransientError("boom")] * 3)
    _patch_client(monkeypatch, client)

    await _run_llm_analysis(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.failed
    assert client.calls == 3


async def test_invalid_response_retried_once_then_failed(clean_jobs_table, monkeypatch):
    job = await _insert_job()
    client = FakeClient([LLMInvalidResponseError("bad json")] * 2)
    _patch_client(monkeypatch, client)

    await _run_llm_analysis(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.failed
    assert client.calls == 2


async def test_already_paused_daily_quota_skips_the_call(clean_jobs_table, monkeypatch):
    job = await _insert_job()
    resume_at = quota_state.set_daily_quota_exhausted()
    client = FakeClient([JobAnalysis(keywords=[])])
    _patch_client(monkeypatch, client)

    await _run_llm_analysis(job.id)

    updated = await _reload(job.id)
    assert updated.processing_status == ProcessingStatus.quota_wait
    assert updated.next_attempt_at == resume_at
    assert client.calls == 0
