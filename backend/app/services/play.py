"""Play sessions: quick quiz and review mode.

Questions are served one at a time. The answer is only ever sent back after the player
has answered, and every answer updates their spaced-repetition (Leitner) state.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.answer_check import RESPONSE_MODELS, mark, response_fits_question
from app.domain.calendar import uk_today
from app.domain.questions import correct_answer_display, shuffle_for_display
from app.domain.selection import pick_quiz_questions
from app.domain.srs import ReviewState, schedule
from app.errors import AppError
from app.models import (
    PlaySession,
    Question,
    QuestionReview,
    SessionAnswer,
    SubjectTopic,
    Topic,
    TopicProgress,
    User,
)
from app.models.enums import PlayMode, QuestionStatus, SessionStatus
from app.schemas.play import (
    AnswerResult,
    Choice,
    Feedback,
    PlayState,
    Progress,
    ResultRow,
    ReviewInfo,
    ServedQuestion,
    Summary,
    TopicRef,
)

QUIZ_LENGTH = 10
REVIEW_LENGTH = 20


def _not_found() -> AppError:
    return AppError(404, "That game doesn't exist.", code="not_found")


# --- starting -------------------------------------------------------------------------------


async def _reviews_for(
    db: AsyncSession, user_id: int, question_ids: list[int]
) -> dict[int, ReviewState]:
    if not question_ids:
        return {}
    rows = await db.execute(
        select(QuestionReview.question_id, QuestionReview.box, QuestionReview.due_on).where(
            QuestionReview.user_id == user_id, QuestionReview.question_id.in_(question_ids)
        )
    )
    return {qid: ReviewState(box, due) for qid, box, due in rows}


async def _touch_topic(
    db: AsyncSession, user_id: int, topic_id: int, subject_id: int | None, now: datetime
) -> None:
    values: dict[str, Any] = {"last_played_at": now}
    if subject_id is not None:
        values["last_subject_id"] = subject_id
    stmt = insert(TopicProgress).values(user_id=user_id, topic_id=topic_id, **values)
    await db.execute(
        stmt.on_conflict_do_update(index_elements=["user_id", "topic_id"], set_=values)
    )


async def start_quiz(
    db: AsyncSession,
    user: User,
    *,
    topic_id: int,
    subject_id: int | None,
    include_higher: bool,
    now: datetime,
    rng: random.Random | None = None,
) -> PlayState:
    rng = rng or random.Random()
    topic = await db.get(Topic, topic_id)
    if topic is None or not topic.is_active:
        raise AppError(404, "That topic doesn't exist.", code="not_found")

    excludes_triple = False
    if subject_id is not None:
        link = await db.get(SubjectTopic, (subject_id, topic_id))
        if link is None:
            raise AppError(404, "That topic isn't part of that subject.", code="not_found")
        excludes_triple = link.excludes_triple_only

    conditions = [
        Question.topic_id == topic_id,
        Question.set_id.is_(None),
        Question.status == QuestionStatus.LIVE,
    ]
    if excludes_triple:
        conditions.append(Question.triple_only.is_(False))
    if not include_higher:
        conditions.append(Question.higher_only.is_(False))
    pool = list(await db.scalars(select(Question.id).where(and_(*conditions))))
    if not pool:
        raise AppError(409, "There aren't any questions for this topic yet.", code="no_questions")

    reviews = await _reviews_for(db, user.id, pool)
    chosen = pick_quiz_questions(pool, reviews, uk_today(now), QUIZ_LENGTH, rng)
    session = PlaySession(
        id=uuid.uuid4(),
        user_id=user.id,
        mode=PlayMode.QUIZ,
        subject_id=subject_id,
        topic_id=topic_id,
        include_higher=include_higher,
        question_count=len(chosen),
        question_ids=chosen,
        started_at=now,
    )
    db.add(session)
    await _touch_topic(db, user.id, topic_id, subject_id, now)
    await db.flush()
    await _serve(db, session, 0, now, rng)
    await db.commit()
    return await get_state(db, user, session.id)


async def start_review(
    db: AsyncSession, user: User, *, now: datetime, rng: random.Random | None = None
) -> PlayState:
    rng = rng or random.Random()
    rows = await db.scalars(
        select(QuestionReview.question_id)
        .join(Question, Question.id == QuestionReview.question_id)
        .where(
            QuestionReview.user_id == user.id,
            QuestionReview.due_on <= uk_today(now),
            Question.status == QuestionStatus.LIVE,
        )
        .order_by(QuestionReview.due_on, QuestionReview.box)
        .limit(REVIEW_LENGTH)
    )
    chosen = list(rows)
    if not chosen:
        raise AppError(409, "Nothing to review right now. Nice!", code="nothing_due")
    rng.shuffle(chosen)
    session = PlaySession(
        id=uuid.uuid4(),
        user_id=user.id,
        mode=PlayMode.REVIEW,
        question_count=len(chosen),
        question_ids=chosen,
        started_at=now,
    )
    db.add(session)
    await db.flush()
    await _serve(db, session, 0, now, rng)
    await db.commit()
    return await get_state(db, user, session.id)


# --- serving --------------------------------------------------------------------------------


async def _serve(
    db: AsyncSession, session: PlaySession, position: int, now: datetime, rng: random.Random
) -> SessionAnswer:
    question = await db.get(Question, session.question_ids[position])
    assert question is not None
    row = SessionAnswer(
        session_id=session.id,
        position=position,
        question_id=question.id,
        user_id=session.user_id,
        topic_id=question.topic_id,
        shown=shuffle_for_display(question.type, question.content, rng),
        served_at=now,
    )
    db.add(row)
    await db.flush()
    return row


def _served(row: SessionAnswer, question: Question, topic_name: str) -> ServedQuestion:
    def choices(key: str) -> list[Choice] | None:
        items = row.shown.get(key)
        return [Choice(**c) for c in items] if items is not None else None

    return ServedQuestion(
        position=row.position,
        question_id=question.id,
        type=question.type,
        prompt=question.prompt,
        subtopic=question.subtopic,
        topic_name=topic_name,
        options=choices("options"),
        items=choices("items"),
        left=choices("left"),
        right=choices("right"),
    )


async def _load_session(
    db: AsyncSession, user: User, session_id: uuid.UUID, *, lock: bool = False
) -> PlaySession:
    stmt = select(PlaySession).where(PlaySession.id == session_id)
    if lock:
        stmt = stmt.with_for_update()
    session = await db.scalar(stmt)
    if session is None or session.user_id != user.id:
        raise _not_found()
    return session


async def _rows(db: AsyncSession, session_id: uuid.UUID) -> list[SessionAnswer]:
    return list(
        await db.scalars(
            select(SessionAnswer)
            .where(SessionAnswer.session_id == session_id)
            .order_by(SessionAnswer.position)
        )
    )


def _progress(session: PlaySession, rows: list[SessionAnswer]) -> Progress:
    answered = [r for r in rows if r.answered_at is not None]
    return Progress(
        answered=len(answered),
        correct=sum(1 for r in answered if r.is_correct),
        total=session.question_count,
    )


async def _topic_ref(db: AsyncSession, session: PlaySession) -> TopicRef | None:
    if session.topic_id is None:
        return None
    name = None
    if session.subject_id is not None:
        link = await db.get(SubjectTopic, (session.subject_id, session.topic_id))
        name = link.display_name if link else None
    if name is None:
        topic = await db.get(Topic, session.topic_id)
        name = topic.name if topic else "Topic"
    return TopicRef(id=session.topic_id, name=name)


async def _summary(db: AsyncSession, session: PlaySession, rows: list[SessionAnswer]) -> Summary:
    progress = _progress(session, rows)
    prompts = {
        q.id: q.prompt
        for q in await db.scalars(select(Question).where(Question.id.in_(session.question_ids)))
    }
    return Summary(
        mode=session.mode,
        status=session.status,
        topic=await _topic_ref(db, session),
        subject_id=session.subject_id,
        total=session.question_count,
        answered=progress.answered,
        correct=progress.correct,
        accuracy=round(progress.correct / progress.answered, 3) if progress.answered else None,
        results=[
            ResultRow(
                position=r.position, prompt=prompts.get(r.question_id, ""), correct=r.is_correct
            )
            for r in rows
            if r.answered_at is not None
        ],
        xp_awarded=session.xp_awarded,
    )


async def _current_question(
    db: AsyncSession, session: PlaySession, rows: list[SessionAnswer]
) -> ServedQuestion | None:
    if session.status != SessionStatus.ACTIVE:
        return None
    current = next((r for r in rows if r.answered_at is None), None)
    if current is None:
        return None
    question = await db.get(Question, current.question_id)
    topic = await db.get(Topic, current.topic_id)
    assert question is not None and topic is not None
    name = (await _topic_ref(db, session) or TopicRef(id=topic.id, name=topic.name)).name
    if session.topic_id is None:
        name = topic.name  # review mode mixes topics
    return _served(current, question, name)


async def get_state(db: AsyncSession, user: User, session_id: uuid.UUID) -> PlayState:
    session = await _load_session(db, user, session_id)
    rows = await _rows(db, session.id)
    finished = session.status != SessionStatus.ACTIVE
    return PlayState(
        session_id=session.id,
        mode=session.mode,
        status=session.status,
        topic=await _topic_ref(db, session),
        subject_id=session.subject_id,
        progress=_progress(session, rows),
        question=await _current_question(db, session, rows),
        summary=await _summary(db, session, rows) if finished else None,
    )


# --- answering ------------------------------------------------------------------------------


async def _feedback(
    db: AsyncSession,
    row: SessionAnswer,
    question: Question,
    partial: str | None,
    user_id: int,
    today_value: Any,
) -> Feedback:
    topic = await db.get(Topic, question.topic_id)
    review = await db.get(QuestionReview, (user_id, question.id))
    return Feedback(
        position=row.position,
        correct=bool(row.is_correct),
        partial=partial,
        correct_answer=correct_answer_display(question.type, question.content, question.answer),
        your_response=row.response or {},
        explanation=question.explanation,
        learn_more_url=topic.learn_more_url if topic and not row.is_correct else None,
        review=ReviewInfo(
            box=review.box,
            due_on=review.due_on,
            days_until_due=(review.due_on - today_value).days,
        )
        if review
        else None,
    )


async def answer(
    db: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    *,
    position: int,
    response: dict[str, Any],
    now: datetime,
    rng: random.Random | None = None,
) -> AnswerResult:
    rng = rng or random.Random()
    today = uk_today(now)
    session = await _load_session(db, user, session_id, lock=True)
    row = await db.get(SessionAnswer, (session.id, position))
    if row is None:
        raise AppError(409, "That question hasn't come up yet.", code="not_served")
    question = await db.get(Question, row.question_id)
    assert question is not None

    if row.answered_at is not None:
        # A retry or double-tap: give back the same result instead of an error.
        rows = await _rows(db, session.id)
        replay = mark(
            question.type,
            question.answer,
            RESPONSE_MODELS[question.type].model_validate(row.response),
            case_sensitive=question.case_sensitive,
        )
        return await _result(db, session, rows, row, question, replay.partial, user.id, today)

    if session.status != SessionStatus.ACTIVE:
        raise AppError(409, "This game has already ended.", code="session_over")

    try:
        parsed = RESPONSE_MODELS[question.type].model_validate(response)
    except ValidationError as exc:
        raise AppError(422, "That answer isn't in the right format.", code="bad_response") from exc
    if not response_fits_question(question.type, row.shown, parsed):
        raise AppError(422, "That answer doesn't match the question.", code="bad_response")

    marked = mark(question.type, question.answer, parsed, case_sensitive=question.case_sensitive)
    row.answered_at = now
    row.response = parsed.model_dump()
    row.is_correct = marked.correct
    row.response_ms = max(0, int((now - row.served_at).total_seconds() * 1000))

    # Spaced repetition.
    review = await db.get(QuestionReview, (user.id, question.id))
    current = ReviewState(review.box, review.due_on) if review else None
    new = schedule(current, marked.correct, today)
    if review is None:
        db.add(
            QuestionReview(
                user_id=user.id,
                question_id=question.id,
                box=new.box,
                due_on=new.due_on,
                times_right=int(marked.correct),
                times_wrong=int(not marked.correct),
            )
        )
    else:
        review.box, review.due_on = new.box, new.due_on
        review.times_right += int(marked.correct)
        review.times_wrong += int(not marked.correct)

    if marked.correct:
        session.user_score += 1
    session.current_position = position + 1
    await _touch_topic(db, user.id, question.topic_id, session.subject_id, now)

    if session.current_position < session.question_count:
        await _serve(db, session, session.current_position, now, rng)
    else:
        session.status = SessionStatus.FINISHED
        session.finished_at = now
    await db.flush()
    await db.commit()

    rows = await _rows(db, session.id)
    return await _result(db, session, rows, row, question, marked.partial, user.id, today)


async def _result(
    db: AsyncSession,
    session: PlaySession,
    rows: list[SessionAnswer],
    row: SessionAnswer,
    question: Question,
    partial: str | None,
    user_id: int,
    today_value: Any,
) -> AnswerResult:
    finished = session.status != SessionStatus.ACTIVE
    next_row = rows[row.position + 1] if row.position + 1 < len(rows) else None
    next_question = None
    if next_row is not None and next_row.answered_at is None and not finished:
        q = await db.get(Question, next_row.question_id)
        topic = await db.get(Topic, next_row.topic_id)
        assert q is not None and topic is not None
        name = topic.name
        if session.topic_id is not None:
            ref = await _topic_ref(db, session)
            name = ref.name if ref else name
        next_question = _served(next_row, q, name)
    return AnswerResult(
        feedback=await _feedback(db, row, question, partial, user_id, today_value),
        progress=_progress(session, rows),
        next=next_question,
        summary=await _summary(db, session, rows) if finished else None,
    )


async def end_early(
    db: AsyncSession, user: User, session_id: uuid.UUID, *, now: datetime
) -> Summary:
    session = await _load_session(db, user, session_id, lock=True)
    if session.status == SessionStatus.ACTIVE:
        session.status = SessionStatus.ABANDONED
        session.finished_at = now
        await db.commit()
    return await _summary(db, session, await _rows(db, session.id))
