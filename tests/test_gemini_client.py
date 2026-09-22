from app.services.llm.gemini_client import _looks_daily


class _FakeExc:
    def __init__(self, details):
        self.details = details


def test_looks_daily_when_day_mentioned_without_minute():
    exc = _FakeExc({"error": {"status": "RESOURCE_EXHAUSTED", "message": "PerDay quota exceeded"}})
    assert _looks_daily(exc) is True


def test_not_daily_when_minute_mentioned():
    exc = _FakeExc({"error": {"message": "PerMinute quota exceeded"}})
    assert _looks_daily(exc) is False


def test_ambiguous_defaults_to_per_minute():
    exc = _FakeExc({"error": {"message": "quota exceeded"}})
    assert _looks_daily(exc) is False
