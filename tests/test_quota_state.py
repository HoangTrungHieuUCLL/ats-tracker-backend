from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services import quota_state


def test_next_daily_reset_is_five_minutes_after_la_midnight():
    resume_at = quota_state.next_daily_reset()
    la_time = resume_at.astimezone(ZoneInfo("America/Los_Angeles"))
    assert la_time.hour == 0
    assert la_time.minute == 5


def test_set_and_get_daily_quota_pause():
    assert quota_state.get_daily_quota_pause() is None
    resume_at = quota_state.set_daily_quota_exhausted()
    assert quota_state.get_daily_quota_pause() == resume_at


def test_pause_clears_itself_once_past():
    quota_state._daily_quota_resume_at = datetime.now(UTC) - timedelta(seconds=1)
    assert quota_state.get_daily_quota_pause() is None
