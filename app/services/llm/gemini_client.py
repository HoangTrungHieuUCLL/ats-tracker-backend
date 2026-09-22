from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.services.llm.base import LLMInvalidResponseError, LLMTransientError, QuotaExceeded
from app.services.llm.prompt import SYSTEM_INSTRUCTION, build_user_content
from app.services.llm.schema import JobAnalysis


class GeminiClient:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self.model = model

    async def analyze(self, job_text: str, json_ld_hints: dict | None) -> JobAnalysis:
        content = build_user_content(job_text, json_ld_hints)
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=content,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=JobAnalysis,
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise QuotaExceeded(is_daily=_looks_daily(exc), message=str(exc)) from exc
            raise LLMTransientError(str(exc)) from exc
        except errors.ServerError as exc:
            raise LLMTransientError(str(exc)) from exc
        except TimeoutError as exc:
            raise LLMTransientError("timeout") from exc

        try:
            return JobAnalysis.model_validate_json(response.text)
        except (ValidationError, ValueError) as exc:
            raise LLMInvalidResponseError(str(exc)) from exc


def _looks_daily(exc: Exception) -> bool:
    """Best-effort per-minute vs daily quota classification (section 7.6).

    Falls back to per-minute when the error body doesn't clearly say.
    """
    blob = str(getattr(exc, "details", "")).lower()
    if "day" in blob and "minute" not in blob:
        return True
    return False
