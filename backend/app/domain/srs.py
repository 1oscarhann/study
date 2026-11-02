"""Spaced repetition: a Leitner box system.

    Box:          1    2    3    4     5
    Comes back:   1d   3d   7d   14d   30d (maintenance)

- Wrong (any time)            → box 1, due tomorrow.
- Right when it was due       → up one box (box 5 stays at 5).
- Right but not yet due       → no change. You can't fast-track a card by re-playing the
                                same quiz; it only moves up when it's actually reviewed.
- First ever sighting, right  → box 4: one light check-in after two weeks, so easy
                                questions don't flood the review queue.

Why Leitner and not SM-2: answers here are right/wrong. SM-2 wants a 0-5 "how well did
you know it" grade that we'd have to fake. Leitner gives the 1/3/7/14-day schedule
directly and is easy to explain ("this comes back in 3 days").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_BOX = 5
FIRST_TIME_CORRECT_BOX = 4


@dataclass(frozen=True)
class ReviewState:
    box: int
    due_on: date


def schedule(current: ReviewState | None, correct: bool, today: date) -> ReviewState:
    """The new state after answering a question on `today` (a UK date)."""
    if current is None:
        box = FIRST_TIME_CORRECT_BOX if correct else 1
    elif not correct:
        box = 1
    elif current.due_on > today:
        return current  # right, but early: no promotion
    else:
        box = min(current.box + 1, MAX_BOX)
    return ReviewState(box=box, due_on=today + timedelta(days=INTERVAL_DAYS[box]))
