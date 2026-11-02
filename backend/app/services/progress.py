"""Catalogue browsing with personal stats, weak spots, the home screen, exam countdowns."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.calendar import uk_today
from app.domain.year_group import status_for
from app.errors import AppError
from app.models import (
    ExamDate,
    Question,
    QuestionReview,
    SessionAnswer,
    Subject,
    SubjectTopic,
    Topic,
    TopicProgress,
    User,
)
from app.models.enums import QuestionStatus
from app.schemas.catalog import (
    Exam,
    ExamIn,
    MyTopicStats,
    SubjectDetail,
    SubjectSummary,
    Subtopic,
    TopicDetail,
    TopicSummary,
)
from app.schemas.progress import (
    DueReviews,
    Home,
    HomeUser,
    RecentTopic,
    WeakSpot,
    WeakSpots,
)

STATS_WINDOW_DAYS = 60
WEAK_SPOT_MIN_ANSWERS = 5
MAX_EXAMS = 20
_LABEL_RE = re.compile(r"^[A-Za-z0-9 .,'&()/:+-]{1,40}$")


# --- shared helpers -------------------------------------------------------------------------


async def topic_stats(db: AsyncSession, user_id: int, now: datetime) -> dict[int, tuple[int, int]]:
    """{topic_id: (answered, correct)} over the stats window."""
    since = now - timedelta(days=STATS_WINDOW_DAYS)
    rows = await db.execute(
        select(
            SessionAnswer.topic_id,
            func.count(),
            func.sum(case((SessionAnswer.is_correct, 1), else_=0)),
        )
        .where(SessionAnswer.user_id == user_id, SessionAnswer.answered_at >= since)
        .group_by(SessionAnswer.topic_id)
    )
    return {tid: (n, int(c or 0)) for tid, n, c in rows}


def _stats(pair: tuple[int, int] | None) -> MyTopicStats:
    answered, correct = pair or (0, 0)
    return MyTopicStats(
        answered=answered,
        correct=correct,
        accuracy=round(correct / answered, 3) if answered else None,
    )


async def _question_counts(db: AsyncSession) -> dict[int, tuple[int, int, int]]:
    """{topic_id: (live total, live non-triple, live higher-only)} for official questions."""
    rows = await db.execute(
        select(
            Question.topic_id,
            func.count(),
            func.sum(case((Question.triple_only, 0), else_=1)),
            func.sum(case((Question.higher_only, 1), else_=0)),
        )
        .where(Question.set_id.is_(None), Question.status == QuestionStatus.LIVE)
        .group_by(Question.topic_id)
    )
    return {tid: (int(t), int(nt or 0), int(h or 0)) for tid, t, nt, h in rows}


def _count_for(counts: dict[int, tuple[int, int, int]], topic_id: int, excludes: bool) -> int:
    total, non_triple, _ = counts.get(topic_id, (0, 0, 0))
    return non_triple if excludes else total


# --- catalogue ------------------------------------------------------------------------------


async def list_subjects(db: AsyncSession) -> list[SubjectSummary]:
    counts = await _question_counts(db)
    links = (
        await db.execute(
            select(
                SubjectTopic.subject_id, SubjectTopic.topic_id, SubjectTopic.excludes_triple_only
            )
            .join(Topic, Topic.id == SubjectTopic.topic_id)
            .where(Topic.is_active)
        )
    ).all()
    per_subject: dict[int, list[tuple[int, bool]]] = {}
    for sid, tid, excl in links:
        per_subject.setdefault(sid, []).append((tid, excl))

    subjects = await db.scalars(
        select(Subject).where(Subject.is_active).order_by(Subject.sort_order, Subject.name)
    )
    return [
        SubjectSummary(
            id=s.id,
            slug=s.slug,
            name=s.name,
            qualification=s.qualification,
            exam_board=s.exam_board,
            topic_count=len(per_subject.get(s.id, [])),
            playable_topic_count=sum(
                1 for tid, excl in per_subject.get(s.id, []) if _count_for(counts, tid, excl) > 0
            ),
        )
        for s in subjects
    ]


async def subject_detail(
    db: AsyncSession, user: User, subject_id: int, now: datetime
) -> SubjectDetail:
    subject = await db.get(Subject, subject_id)
    if subject is None or not subject.is_active:
        raise AppError(404, "That subject doesn't exist.", code="not_found")
    counts = await _question_counts(db)
    stats = await topic_stats(db, user.id, now)
    played = dict(
        (
            await db.execute(
                select(TopicProgress.topic_id, TopicProgress.last_played_at).where(
                    TopicProgress.user_id == user.id
                )
            )
        ).all()
    )
    rows = await db.execute(
        select(SubjectTopic, Topic)
        .join(Topic, Topic.id == SubjectTopic.topic_id)
        .where(SubjectTopic.subject_id == subject_id, Topic.is_active)
        .order_by(SubjectTopic.sort_order)
    )
    return SubjectDetail(
        id=subject.id,
        slug=subject.slug,
        name=subject.name,
        qualification=subject.qualification,
        exam_board=subject.exam_board,
        spec_code=subject.spec_code,
        topics=[
            TopicSummary(
                topic_id=topic.id,
                slug=topic.slug,
                name=link.display_name,
                spec_ref=link.spec_ref,
                question_count=_count_for(counts, topic.id, link.excludes_triple_only),
                stats=_stats(stats.get(topic.id)),
                last_played_at=played.get(topic.id),
            )
            for link, topic in rows
        ],
    )


async def topic_detail(
    db: AsyncSession, user: User, topic_id: int, subject_id: int | None, now: datetime
) -> TopicDetail:
    topic = await db.get(Topic, topic_id)
    if topic is None or not topic.is_active:
        raise AppError(404, "That topic doesn't exist.", code="not_found")
    link = await db.get(SubjectTopic, (subject_id, topic_id)) if subject_id else None
    if subject_id is not None and link is None:
        raise AppError(404, "That topic isn't part of that subject.", code="not_found")
    subject = await db.get(Subject, subject_id) if subject_id else None
    excludes = bool(link and link.excludes_triple_only)
    counts = await _question_counts(db)
    _, _, higher = counts.get(topic_id, (0, 0, 0))

    today = uk_today(now)
    due = await db.scalar(
        select(func.count())
        .select_from(QuestionReview)
        .join(Question, Question.id == QuestionReview.question_id)
        .where(
            QuestionReview.user_id == user.id,
            QuestionReview.due_on <= today,
            Question.topic_id == topic_id,
            Question.status == QuestionStatus.LIVE,
        )
    )
    progress = await db.get(TopicProgress, (user.id, topic_id))
    stats = await topic_stats(db, user.id, now)
    subtopics = [
        Subtopic(**s)
        for s in topic.subtopics
        if not (excludes and s.get("triple_only"))  # Combined students don't see triple-only
    ]
    return TopicDetail(
        topic_id=topic.id,
        slug=topic.slug,
        name=link.display_name if link else topic.name,
        subject_id=subject.id if subject else None,
        subject_name=subject.name if subject else None,
        spec_ref=link.spec_ref if link else None,
        subtopics=subtopics,
        learn_more_url=topic.learn_more_url,
        question_count=_count_for(counts, topic_id, excludes),
        higher_only_count=higher,
        due_count=due or 0,
        stats=_stats(stats.get(topic_id)),
        last_played_at=progress.last_played_at if progress else None,
    )


# --- weak spots / home ----------------------------------------------------------------------


async def _names(
    db: AsyncSession, pairs: list[tuple[int, int | None]]
) -> dict[tuple[int, int | None], tuple[str, str | None, int | None]]:
    """(topic_id, subject_id) → (display name, subject name, subject id), falling back to the
    topic's first subject link when we don't know which subject it was played through."""
    out: dict[tuple[int, int | None], tuple[str, str | None, int | None]] = {}
    for topic_id, subject_id in pairs:
        stmt = (
            select(SubjectTopic.display_name, Subject.name, Subject.id)
            .join(Subject, Subject.id == SubjectTopic.subject_id)
            .where(SubjectTopic.topic_id == topic_id)
        )
        if subject_id is not None:
            stmt = stmt.where(SubjectTopic.subject_id == subject_id)
        row = (await db.execute(stmt.order_by(Subject.sort_order).limit(1))).first()
        if row is None:
            topic = await db.get(Topic, topic_id)
            out[(topic_id, subject_id)] = (topic.name if topic else "Topic", None, None)
        else:
            out[(topic_id, subject_id)] = (row[0], row[1], row[2])
    return out


async def weak_spots(db: AsyncSession, user: User, now: datetime) -> WeakSpots:
    stats = await topic_stats(db, user.id, now)
    progress = {
        p.topic_id: p
        for p in await db.scalars(select(TopicProgress).where(TopicProgress.user_id == user.id))
    }
    pairs = [(tid, progress[tid].last_subject_id if tid in progress else None) for tid in stats]
    names = await _names(db, pairs)
    spots = []
    for tid, subject_id in pairs:
        answered, correct = stats[tid]
        name, subject_name, resolved_subject = names[(tid, subject_id)]
        spots.append(
            WeakSpot(
                topic_id=tid,
                subject_id=resolved_subject,
                name=name,
                subject_name=subject_name,
                answered=answered,
                correct=correct,
                accuracy=round(correct / answered, 3),
                enough_data=answered >= WEAK_SPOT_MIN_ANSWERS,
                last_played_at=progress[tid].last_played_at if tid in progress else None,
            )
        )
    # Worst first among topics with enough answers; the rest after, most-played first.
    spots.sort(key=lambda s: (not s.enough_data, s.accuracy if s.enough_data else 0, -s.answered))
    return WeakSpots(window_days=STATS_WINDOW_DAYS, min_answers=WEAK_SPOT_MIN_ANSWERS, topics=spots)


async def due_reviews(db: AsyncSession, user: User, now: datetime) -> DueReviews:
    today = uk_today(now)
    base = (
        select(func.count())
        .select_from(QuestionReview)
        .join(Question, Question.id == QuestionReview.question_id)
        .where(QuestionReview.user_id == user.id, Question.status == QuestionStatus.LIVE)
    )
    today_count = await db.scalar(base.where(QuestionReview.due_on <= today))
    week_count = await db.scalar(base.where(QuestionReview.due_on <= today + timedelta(days=6)))
    return DueReviews(today=today_count or 0, this_week=week_count or 0)


async def home(db: AsyncSession, user: User, now: datetime) -> Home:
    status = status_for(user.cohort_year, uk_today(now))
    stats = await topic_stats(db, user.id, now)
    recent_rows = list(
        await db.scalars(
            select(TopicProgress)
            .where(TopicProgress.user_id == user.id, TopicProgress.last_played_at.is_not(None))
            .order_by(TopicProgress.last_played_at.desc())
            .limit(3)
        )
    )
    names = await _names(db, [(p.topic_id, p.last_subject_id) for p in recent_rows])
    recent = []
    for p in recent_rows:
        name, subject_name, subject_id = names[(p.topic_id, p.last_subject_id)]
        answered, correct = stats.get(p.topic_id, (0, 0))
        recent.append(
            RecentTopic(
                topic_id=p.topic_id,
                subject_id=subject_id,
                name=name,
                subject_name=subject_name,
                accuracy=round(correct / answered, 3) if answered else None,
                last_played_at=p.last_played_at,  # type: ignore[arg-type]
            )
        )
    spots = (await weak_spots(db, user, now)).topics
    weakest = next((s for s in spots if s.enough_data), None)
    return Home(
        user=HomeUser(
            username=user.username,
            year_group=status.year_group,
            graduated=status.graduated,
            total_xp=user.total_xp,
            streak_current=user.streak_current,
        ),
        due_reviews=await due_reviews(db, user, now),
        recent_topics=recent,
        weakest_topic=weakest,
        exams=(await list_exams(db, user, now))[:5],
    )


# --- exams ----------------------------------------------------------------------------------


async def list_exams(db: AsyncSession, user: User, now: datetime) -> list[Exam]:
    today = uk_today(now)
    rows = await db.execute(
        select(ExamDate, Subject.name)
        .join(Subject, Subject.id == ExamDate.subject_id)
        .where(ExamDate.user_id == user.id, ExamDate.exam_date >= today)
        .order_by(ExamDate.exam_date, ExamDate.id)
    )
    return [
        Exam(
            id=e.id,
            subject_id=e.subject_id,
            subject_name=name,
            label=e.label,
            exam_date=e.exam_date,
            days_left=(e.exam_date - today).days,
        )
        for e, name in rows
    ]


async def add_exam(db: AsyncSession, user: User, body: ExamIn, now: datetime) -> Exam:
    today = uk_today(now)
    if body.exam_date < today:
        raise AppError(422, "That date has already passed.", code="bad_date", field="exam_date")
    if body.exam_date > today + timedelta(days=730):
        raise AppError(422, "Pick a date within the next two years.", code="bad_date",
                       field="exam_date")  # fmt: skip
    label = (body.label or "").strip() or None
    if label and not _LABEL_RE.fullmatch(label):
        raise AppError(422, "Keep the label short and simple, like “Paper 1”.", code="bad_label",
                       field="label")  # fmt: skip
    subject = await db.get(Subject, body.subject_id)
    if subject is None or not subject.is_active:
        raise AppError(422, "Pick a subject from the list.", code="bad_subject", field="subject_id")
    count = await db.scalar(
        select(func.count()).select_from(ExamDate).where(ExamDate.user_id == user.id)
    )
    if (count or 0) >= MAX_EXAMS:
        raise AppError(409, f"You can track up to {MAX_EXAMS} exams.", code="too_many")
    exam = ExamDate(user_id=user.id, subject_id=subject.id, label=label, exam_date=body.exam_date)
    db.add(exam)
    await db.commit()
    return Exam(
        id=exam.id,
        subject_id=subject.id,
        subject_name=subject.name,
        label=label,
        exam_date=exam.exam_date,
        days_left=(exam.exam_date - today).days,
    )


async def delete_exam(db: AsyncSession, user: User, exam_id: int) -> None:
    result = await db.execute(
        delete(ExamDate).where(and_(ExamDate.id == exam_id, ExamDate.user_id == user.id))
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise AppError(404, "That exam doesn't exist.", code="not_found")
    await db.commit()
