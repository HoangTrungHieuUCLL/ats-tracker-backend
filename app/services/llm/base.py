from typing import Protocol

from app.services.llm.schema import JobAnalysis


class QuotaExceeded(Exception):
    def __init__(self, is_daily: bool, message: str = ""):
        self.is_daily = is_daily
        super().__init__(message)


class LLMTransientError(Exception):
    """5xx, timeout, or other transient failure. Retried with backoff."""


class LLMInvalidResponseError(Exception):
    """Response failed schema validation."""


class LLMClient(Protocol):
    async def analyze(self, job_text: str, json_ld_hints: dict | None) -> JobAnalysis: ...
