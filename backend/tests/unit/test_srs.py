"""Leitner scheduling: wrong answers come back after ~1, 3, 7, 14 days."""

from datetime import date, timedelta

import pytest

from app.domain.srs import INTERVAL_DAYS, ReviewState, schedule

TODAY = date(2026, 11, 2)


def days(n: int) -> date:
    return TODAY + timedelta(days=n)


def test_first_time_wrong_comes_back_tomorrow():
    assert schedule(None, correct=False, today=TODAY) == ReviewState(1, days(1))


def test_first_time_right_gets_one_check_in_after_two_weeks():
    assert schedule(None, correct=True, today=TODAY) == ReviewState(4, days(14))


def test_the_spec_schedule_1_3_7_14_days():
    """Get it wrong once, then right at every review: 1 → 3 → 7 → 14 → 30 days."""
    state = schedule(None, correct=False, today=TODAY)
    gaps = [(state.due_on - TODAY).days]
    day = TODAY
    for _ in range(4):
        day = state.due_on
        state = schedule(state, correct=True, today=day)
        gaps.append((state.due_on - day).days)
    assert gaps == [1, 3, 7, 14, 30]


def test_box_5_stays_at_30_days():
    state = ReviewState(5, TODAY)
    assert schedule(state, correct=True, today=TODAY) == ReviewState(5, days(30))


@pytest.mark.parametrize("box", [1, 2, 3, 4, 5])
def test_wrong_answer_always_goes_back_to_box_1(box):
    assert schedule(ReviewState(box, TODAY), correct=False, today=TODAY) == ReviewState(1, days(1))


def test_wrong_answer_before_due_still_resets():
    state = ReviewState(4, days(10))
    assert schedule(state, correct=False, today=TODAY) == ReviewState(1, days(1))


def test_right_answer_before_due_doesnt_fast_track():
    state = ReviewState(2, days(2))
    assert schedule(state, correct=True, today=TODAY) == state


def test_overdue_review_promotes_from_today():
    state = ReviewState(2, TODAY - timedelta(days=5))
    assert schedule(state, correct=True, today=TODAY) == ReviewState(3, days(7))


def test_intervals_match_the_spec():
    assert [INTERVAL_DAYS[b] for b in range(1, 6)] == [1, 3, 7, 14, 30]
