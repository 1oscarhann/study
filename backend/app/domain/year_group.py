"""Year groups from a stored cohort, so everyone moves up automatically on 1 September.

We never store "Year 10". We store `cohort_year`: the calendar year of the September
the student started (or would have started) Year 7. Then:

    year_group = 7 + academic_year_start(today) - cohort_year

Anyone past Year 13 is "graduated": they can still revise, but they're hidden from
leaderboards and leagues.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.calendar import academic_year_start

FIRST_YEAR = 7
LAST_YEAR = 13
YEAR_GROUPS = tuple(range(FIRST_YEAR, LAST_YEAR + 1))


@dataclass(frozen=True)
class YearGroupStatus:
    year_group: int | None  # None once graduated
    graduated: bool


def _check_year(year_group: int) -> None:
    if year_group not in YEAR_GROUPS:
        raise ValueError(f"Year group must be {FIRST_YEAR}-{LAST_YEAR}, got {year_group}")


def cohort_for(year_group: int, today: date) -> int:
    """The cohort for someone who is in `year_group` on `today`."""
    _check_year(year_group)
    return academic_year_start(today) - (year_group - FIRST_YEAR)


def raw_year_group(cohort_year: int, today: date) -> int:
    return FIRST_YEAR + academic_year_start(today) - cohort_year


def status_for(cohort_year: int, today: date) -> YearGroupStatus:
    year = raw_year_group(cohort_year, today)
    if year > LAST_YEAR:
        return YearGroupStatus(year_group=None, graduated=True)
    # Below Year 7 can't happen via signup; clamp rather than show nonsense.
    return YearGroupStatus(year_group=max(year, FIRST_YEAR), graduated=False)


def can_correct(year_group_changed_for: int | None, today: date) -> bool:
    """One correction per academic year (stops leaderboard farming)."""
    return year_group_changed_for is None or year_group_changed_for < academic_year_start(today)
