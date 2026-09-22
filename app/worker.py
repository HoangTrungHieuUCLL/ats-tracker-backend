import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import and_, or_, select, update

from app.config import settings
from app.db import async_session_maker
from app.models import ExtractionMethod, Job, ProcessingStatus
from app.services.extraction.ats_adapters import fetch_ats_text, match_ats
from app.services.extraction.json_ld import extract_json_ld_job_posting
from app.services.extraction.quality_gate import clean_text, passes_quality_gate
from app.services.extraction.readability import extract_main_content
from app.services.fetch import FetchBlocked, FetchTooLarge, FetchTransientError, fetch_page
from app.services.llm.base import LLMInvalidResponseError, LLMTransientError, QuotaExceeded
from app.services.llm.gemini_client import GeminiClient
from app.services.postprocess import apply_analysis
from app.services.quota_state import get_daily_quota_pause, set_daily_quota_exhausted

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [10, 30, 90]
STUCK_RESET_MINUTES = 10

LLM_MAX_ATTEMPTS = 3
LLM_PER_MINUTE_BACKOFF_SECONDS = [15, 30, 60]


class DomainRateLimiter:
    def __init__(self, min_seconds: float):
        self.min_seconds = min_seconds
        self._last_request_at: dict[str, float] = {}

    async def wait(self, domain: str) -> None:
        now = time.monotonic()
        last = self._last_request_at.get(domain)
        if last is not None:
            remaining = self.min_seconds - (now - last)
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at[domain] = time.monotonic()


class MinIntervalLimiter:
    """Like DomainRateLimiter, but a single global interval (used for the LLM)."""

    def __init__(self, min_seconds: float):
        self.min_seconds = min_seconds
        self._last_at: float | None = None

    async def wait(self) -> None:
        now = time.monotonic()
        if self._last_at is not None:
            remaining = self.min_seconds - (now - self._last_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_at = time.monotonic()


_limiter = DomainRateLimiter(settings.fetch_min_seconds_per_domain)
_llm_limiter = MinIntervalLimiter(settings.llm_min_seconds_between_calls)
_llm_client: GeminiClient | None = None


def _get_llm_client() -> GeminiClient | None:
    global _llm_client
    if not settings.gemini_api_key:
        return None
    if _llm_client is None:
        _llm_client = GeminiClient(api_key=settings.gemini_api_key, model=settings.llm_model)
    return _llm_client


async def reset_stuck_jobs() -> None:
    cutoff = datetime.now(UTC) - timedelta(minutes=STUCK_RESET_MINUTES)
    async with async_session_maker() as session:
        stmt = (
            update(Job)
            .where(
                Job.processing_status.in_(
                    [
                        ProcessingStatus.fetching,
                        ProcessingStatus.extracting,
                        ProcessingStatus.analyzing,
                    ]
                ),
                Job.updated_at < cutoff,
            )
            .values(processing_status=ProcessingStatus.queued)
        )
        await session.execute(stmt)
        await session.commit()


async def claim_next_job() -> uuid.UUID | None:
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        stmt = (
            select(Job)
            .where(
                or_(
                    Job.processing_status == ProcessingStatus.queued,
                    and_(
                        Job.processing_status == ProcessingStatus.quota_wait,
                        Job.next_attempt_at.isnot(None),
                        Job.next_attempt_at <= now,
                    ),
                )
            )
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await session.execute(stmt)).scalar_one_or_none()
        if job is None:
            return None
        job.processing_status = ProcessingStatus.fetching
        await session.commit()
        return job.id


async def _set_status(job_id: uuid.UUID, status: ProcessingStatus) -> None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.processing_status = status
            await session.commit()


async def _mark_needs_manual_text(job_id: uuid.UUID, reason: str) -> None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.processing_status = ProcessingStatus.needs_manual_text
            job.processing_error = reason
            await session.commit()


async def _mark_failed(job_id: uuid.UUID, reason: str) -> None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.processing_status = ProcessingStatus.failed
            job.processing_error = reason
            await session.commit()


async def _set_quota_wait(job_id: uuid.UUID, resume_at) -> None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.processing_status = ProcessingStatus.quota_wait
            job.next_attempt_at = resume_at
            job.processing_error = "Gemini daily quota reached."
            await session.commit()


async def _bump_attempts(job_id: uuid.UUID) -> None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.attempts += 1
            await session.commit()


def _truncation_warning(truncated: bool) -> str | None:
    return "Extracted text was truncated to 20,000 characters." if truncated else None


async def _run_extraction_ladder(html: str, url: str):
    """Returns (text, ExtractionMethod, hints, warning) for the first step that
    passes the quality gate (section 7.2), or None if all steps fail it."""
    json_ld_result = extract_json_ld_job_posting(html)
    hints = json_ld_result["hints"] if json_ld_result else None
    if json_ld_result and json_ld_result["text"] and passes_quality_gate(json_ld_result["text"]):
        cleaned, truncated = clean_text(json_ld_result["text"])
        return cleaned, ExtractionMethod.json_ld, hints, _truncation_warning(truncated)

    match = match_ats(url)
    if match:
        domain = urlsplit(match.fetch_url).netloc
        await _limiter.wait(domain)
        async with httpx.AsyncClient() as client:
            text = await fetch_ats_text(client, match, url)
        if text and passes_quality_gate(text):
            cleaned, truncated = clean_text(text)
            return cleaned, ExtractionMethod.ats_api, hints, _truncation_warning(truncated)

    text = extract_main_content(html)
    if text and passes_quality_gate(text):
        cleaned, truncated = clean_text(text)
        return cleaned, ExtractionMethod.readability, hints, _truncation_warning(truncated)

    return None


async def _call_llm_with_validation(client: GeminiClient, raw_text: str, hints):
    """Retry once on schema-validation failure (section 7.5.1), then propagate."""
    last_exc: LLMInvalidResponseError | None = None
    for _ in range(2):
        try:
            return await client.analyze(raw_text, hints)
        except LLMInvalidResponseError as exc:
            last_exc = exc
    raise last_exc


async def _run_llm_analysis(job_id: uuid.UUID) -> None:
    pause_until = get_daily_quota_pause()
    if pause_until is not None:
        await _set_quota_wait(job_id, pause_until)
        return

    client = _get_llm_client()
    if client is None:
        await _mark_failed(job_id, "GEMINI_API_KEY is not configured")
        return

    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        raw_text = job.raw_text
        hints = job.json_ld_hints

    analysis = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        await _llm_limiter.wait()
        try:
            analysis = await _call_llm_with_validation(client, raw_text, hints)
            break
        except QuotaExceeded as exc:
            if exc.is_daily or attempt >= LLM_MAX_ATTEMPTS:
                resume_at = set_daily_quota_exhausted()
                await _set_quota_wait(job_id, resume_at)
                return
            await asyncio.sleep(LLM_PER_MINUTE_BACKOFF_SECONDS[attempt - 1])
        except LLMTransientError as exc:
            if attempt >= LLM_MAX_ATTEMPTS:
                reason = f"LLM call failed after {LLM_MAX_ATTEMPTS} attempts: {exc}"
                await _mark_failed(job_id, reason)
                return
            await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
        except LLMInvalidResponseError as exc:
            await _mark_failed(job_id, f"LLM response failed validation: {exc}")
            return

    if analysis is None:
        return

    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        await apply_analysis(session, job, analysis, client.model)


async def process_job(job_id: uuid.UUID) -> None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        domain = job.domain
        source_url = job.source_url

    html: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        await _bump_attempts(job_id)
        await _limiter.wait(domain)
        try:
            async with httpx.AsyncClient() as client:
                html = await fetch_page(client, source_url)
            break
        except FetchBlocked as exc:
            await _mark_needs_manual_text(job_id, f"Blocked while fetching: {exc}")
            return
        except FetchTooLarge as exc:
            await _mark_needs_manual_text(job_id, str(exc))
            return
        except FetchTransientError as exc:
            if attempt >= MAX_ATTEMPTS:
                await _mark_failed(job_id, f"Fetch failed after {MAX_ATTEMPTS} attempts: {exc}")
                return
            await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])

    if html is None:
        return

    await _set_status(job_id, ProcessingStatus.extracting)

    extraction = await _run_extraction_ladder(html, source_url)
    if extraction is None:
        await _mark_needs_manual_text(job_id, "No extraction method produced usable text")
        return

    text, method, hints, warning = extraction
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        job.raw_text = text
        job.raw_text_chars = len(text)
        job.extraction_method = method
        job.json_ld_hints = hints
        job.processing_error = warning
        job.processing_status = ProcessingStatus.analyzing
        await session.commit()

    await _run_llm_analysis(job_id)


async def worker_loop() -> None:
    await reset_stuck_jobs()
    while True:
        try:
            job_id = await claim_next_job()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("claim_next_job failed")
            job_id = None

        if job_id is None:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            await process_job(job_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("process_job failed for %s", job_id)
            await _mark_failed(job_id, "Unexpected worker error")
