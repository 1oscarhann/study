"""UK time helpers. Every "day", "week" and "school year" in the app means UK time.

The academic year starts on 1 September; weeks start on Monday 00:00 (Europe/London).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")


def utc_now() -> datetime:
    return datetime.now(UTC)


def uk_today(now: datetime | None = None) -> date:
    """Today's date in the UK. `now` must be timezone-aware."""
    now = now or utc_now()
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(UK_TZ).date()


def academic_year_start(day: date) -> int:
    """Calendar year in which the academic year containing `day` began (1 Sept)."""
    return day.year if day.month >= 9 else day.year - 1


def week_start(day: date) -> date:
    """The Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())
