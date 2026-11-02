"""Year groups roll over at 00:00 on 1 September, UK time (BST in September)."""

from datetime import UTC, date, datetime

import pytest

from app.domain.calendar import academic_year_start, uk_today, week_start
from app.domain.year_group import (
    YearGroupStatus,
    can_correct,
    cohort_for,
    raw_year_group,
    status_for,
)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 8, 31), 2025),
        (date(2026, 9, 1), 2026),
        (date(2026, 12, 31), 2026),
        (date(2027, 1, 1), 2026),
        (date(2027, 7, 20), 2026),
        (date(2028, 2, 29), 2027),  # leap day
    ],
)
def test_academic_year_starts_on_1_september(day, expected):
    assert academic_year_start(day) == expected


@pytest.mark.parametrize(
    ("utc_iso", "uk_date"),
    [
        # 23:30 UTC on 31 Aug is 00:30 BST on 1 Sept: already the new school year.
        ("2027-08-31T23:30:00+00:00", date(2027, 9, 1)),
        ("2027-08-31T22:59:59+00:00", date(2027, 8, 31)),
        # In winter (GMT) UTC and UK dates match.
        ("2026-12-31T23:59:00+00:00", date(2026, 12, 31)),
        # Clocks go back 25 Oct 2026: 23:30 UTC on the 24th is 00:30 BST on the 25th.
        ("2026-10-24T23:30:00+00:00", date(2026, 10, 25)),
    ],
)
def test_uk_today_uses_london_time(utc_iso, uk_date):
    assert uk_today(datetime.fromisoformat(utc_iso)) == uk_date


def test_uk_today_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        uk_today(datetime(2026, 9, 1, 12, 0))


def test_signup_in_year_10_moves_up_on_1_september():
    cohort = cohort_for(10, date(2026, 11, 2))
    assert cohort == 2023
    assert status_for(cohort, date(2027, 8, 31)) == YearGroupStatus(10, graduated=False)
    assert status_for(cohort, date(2027, 9, 1)) == YearGroupStatus(11, graduated=False)


def test_signup_during_summer_holidays_uses_the_year_just_finished():
    # On 15 Aug a student who just finished Year 9 is still Year 9 until 1 Sept.
    cohort = cohort_for(9, date(2027, 8, 15))
    assert status_for(cohort, date(2027, 8, 31)).year_group == 9
    assert status_for(cohort, date(2027, 9, 1)).year_group == 10


def test_year_13_graduates_on_1_september():
    cohort = cohort_for(13, date(2027, 3, 1))
    assert status_for(cohort, date(2027, 8, 31)) == YearGroupStatus(13, graduated=False)
    assert status_for(cohort, date(2027, 9, 1)) == YearGroupStatus(None, graduated=True)
    assert status_for(cohort, date(2035, 1, 1)).graduated


@pytest.mark.parametrize("year", range(7, 14))
def test_cohort_round_trips_for_every_year_group(year):
    today = date(2026, 11, 2)
    assert raw_year_group(cohort_for(year, today), today) == year


@pytest.mark.parametrize("bad", [6, 14, 0, -1])
def test_only_years_7_to_13_are_allowed(bad):
    with pytest.raises(ValueError):
        cohort_for(bad, date(2026, 11, 2))


def test_below_year_7_is_clamped_not_shown():
    # Can't happen via signup, but a clock going backwards shouldn't show "Year 6".
    cohort = cohort_for(7, date(2026, 9, 1))
    assert status_for(cohort, date(2026, 8, 31)).year_group == 7


def test_one_correction_per_academic_year():
    assert can_correct(None, date(2026, 11, 2))
    # Corrected during 2026/27 → locked for the rest of that school year…
    assert not can_correct(2026, date(2026, 11, 3))
    assert not can_correct(2026, date(2027, 8, 31))
    # …and unlocked from 1 September.
    assert can_correct(2026, date(2027, 9, 1))


def test_week_starts_on_monday():
    assert week_start(date(2026, 11, 4)) == date(2026, 11, 2)  # Wed → Mon
    assert week_start(date(2026, 11, 2)) == date(2026, 11, 2)
    assert week_start(date(2026, 11, 8)) == date(2026, 11, 2)  # Sun → Mon


def test_aware_now_in_utc_is_fine():
    assert uk_today(datetime(2026, 6, 1, 12, tzinfo=UTC)) == date(2026, 6, 1)
