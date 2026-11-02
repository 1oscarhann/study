"""Which questions go into a quick quiz.

Priority, each bucket shuffled:
  1. due for review in this topic       (spaced repetition first)
  2. never seen                         (cover new material)
  3. shaky: in box 1-2 but not yet due  (recently got wrong)
  4. everything else                    (known, not due)
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import date

from app.domain.srs import ReviewState


def pick_quiz_questions(
    pool: Iterable[int],
    reviews: dict[int, ReviewState],
    today: date,
    count: int,
    rng: random.Random,
) -> list[int]:
    due: list[int] = []
    unseen: list[int] = []
    shaky: list[int] = []
    rest: list[int] = []
    for qid in pool:
        state = reviews.get(qid)
        if state is None:
            unseen.append(qid)
        elif state.due_on <= today:
            due.append(qid)
        elif state.box <= 2:
            shaky.append(qid)
        else:
            rest.append(qid)
    picked: list[int] = []
    for bucket in (due, unseen, shaky, rest):
        rng.shuffle(bucket)
        picked.extend(bucket)
    chosen = picked[:count]
    # Shuffle the final set too, so due ones aren't always at the start.
    rng.shuffle(chosen)
    return chosen
