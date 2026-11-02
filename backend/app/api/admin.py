"""Admin-only: the official topic list and official questions.

Admins are made with `python -m app.cli make-admin USERNAME`; there's no way to become
one through the API.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser
from app.content.catalog import ImportFile, build_catalog, merge_files
from app.db import DbSession
from app.domain.questions import QuestionDraft, to_storage
from app.errors import AppError
from app.models import Question, SessionAnswer, Subject, Topic, User
from app.models.enums import QuestionOrigin, QuestionStatus, VerificationStatus
from app.services.content import apply_catalog


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise AppError(403, "Admins only.", code="forbidden")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
router = APIRouter(prefix="/admin", tags=["admin"])


class SubjectPatch(BaseModel):
    is_active: bool | None = None


class TopicPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    learn_more_url: HttpUrl | None = None
    clear_learn_more_url: bool = False
    is_active: bool | None = None


class AdminTopic(BaseModel):
    id: int
    slug: str
    name: str
    learn_more_url: str | None
    is_active: bool


class AdminQuestion(BaseModel):
    id: int
    topic_id: int
    type: str
    prompt: str
    content: dict[str, Any]
    answer: dict[str, Any]
    explanation: str
    status: str
    origin: str
    difficulty: int
    is_core: bool
    report_count: int


class NewQuestion(BaseModel):
    topic_id: int
    question: QuestionDraft


def _admin_question(q: Question) -> AdminQuestion:
    return AdminQuestion(
        id=q.id,
        topic_id=q.topic_id,
        type=q.type,
        prompt=q.prompt,
        content=q.content,
        answer=q.answer,
        explanation=q.explanation,
        status=q.status,
        origin=q.origin,
        difficulty=q.difficulty,
        is_core=q.is_core,
        report_count=q.report_count,
    )


@router.patch("/subjects/{subject_id}")
async def patch_subject(
    subject_id: int, body: SubjectPatch, _: AdminUser, db: DbSession
) -> dict[str, Any]:
    subject = await db.get(Subject, subject_id)
    if subject is None:
        raise AppError(404, "No such subject.", code="not_found")
    if body.is_active is not None:
        subject.is_active = body.is_active
    await db.commit()
    return {"id": subject.id, "is_active": subject.is_active}


@router.post("/topics/import")
async def import_topics(body: ImportFile, _: AdminUser, db: DbSession) -> dict[str, int]:
    """Upload a topic file in the same format as backend/seed/gcse_topics.json."""
    stats = await apply_catalog(db, build_catalog(merge_files([body])))
    await db.commit()
    return stats.as_dict()


@router.patch("/topics/{topic_id}")
async def patch_topic(topic_id: int, body: TopicPatch, _: AdminUser, db: DbSession) -> AdminTopic:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise AppError(404, "No such topic.", code="not_found")
    if body.name is not None:
        topic.name = body.name
    if body.clear_learn_more_url:
        topic.learn_more_url = None
    elif body.learn_more_url is not None:
        if body.learn_more_url.scheme != "https":
            raise AppError(422, "Links must start with https://", code="bad_url",
                           field="learn_more_url")  # fmt: skip
        topic.learn_more_url = str(body.learn_more_url)
    if body.is_active is not None:
        topic.is_active = body.is_active
    await db.commit()
    return AdminTopic(
        id=topic.id,
        slug=topic.slug,
        name=topic.name,
        learn_more_url=topic.learn_more_url,
        is_active=topic.is_active,
    )


@router.get("/questions")
async def list_questions(
    _: AdminUser, db: DbSession, topic_id: int = Query()
) -> list[AdminQuestion]:
    rows = await db.scalars(
        select(Question)
        .where(Question.topic_id == topic_id, Question.set_id.is_(None))
        .order_by(Question.id)
    )
    return [_admin_question(q) for q in rows]


@router.post("/questions", status_code=status.HTTP_201_CREATED)
async def add_question(body: NewQuestion, admin: AdminUser, db: DbSession) -> AdminQuestion:
    if await db.get(Topic, body.topic_id) is None:
        raise AppError(404, "No such topic.", code="not_found", field="topic_id")
    draft = body.question
    stored = to_storage(draft)
    q = Question(
        topic_id=body.topic_id,
        type=stored.type,
        prompt=draft.prompt,
        content=stored.content,
        answer=stored.answer,
        explanation=draft.explanation,
        subtopic=draft.subtopic,
        difficulty=draft.difficulty,
        is_core=draft.is_core,
        higher_only=draft.higher_only,
        triple_only=draft.triple_only,
        case_sensitive=getattr(draft, "case_sensitive", False),
        status=QuestionStatus.LIVE,
        origin=QuestionOrigin.ADMIN,
        verification=VerificationStatus.PASSED,
        created_by=admin.id,
        approved_by=admin.id,
    )
    db.add(q)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(409, "That topic already has a question with this prompt.",
                       code="duplicate", field="prompt") from exc  # fmt: skip
    return _admin_question(q)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_question(question_id: int, _: AdminUser, db: DbSession) -> None:
    q = await db.get(Question, question_id)
    if q is None or q.set_id is not None:
        raise AppError(404, "No such official question.", code="not_found")
    answered = await db.scalar(select(exists().where(SessionAnswer.question_id == q.id)))
    if answered:
        q.status = QuestionStatus.ARCHIVED  # keep history and stats intact
    else:
        await db.delete(q)
    await db.commit()
