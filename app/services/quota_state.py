from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

_LA_TZ = ZoneInfo("America/Los_Angeles")

_daily_quota_resume_at: datetime | None = None


def next_daily_reset() -> datetime:
    """Next midnight America/Los_Angeles + 5 minutes, as a UTC-aware datetime."""
    now_la = datetime.now(_LA_TZ)
    next_midnight_la = (now_la + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    resume_at_la = next_midnight_la + timedelta(minutes=5)
    return resume_at_la.astimezone(UTC)


def set_daily_quota_exhausted() -> datetime:
    global _daily_quota_resume_at
    _daily_quota_resume_at = next_daily_reset()
    return _daily_quota_resume_at


def get_daily_quota_pause() -> datetime | None:
    """Returns the resume time if the daily quota is currently paused, else None."""
    global _daily_quota_resume_at
    if _daily_quota_resume_at is not None and datetime.now(UTC) >= _daily_quota_resume_at:
        _daily_quota_resume_at = None
    return _daily_quota_resume_at
