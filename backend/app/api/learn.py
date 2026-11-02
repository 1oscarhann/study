"""Catalogue, play sessions, progress, home and exam countdowns."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, Now
from app.db import DbSession
from app.schemas.catalog import Exam, ExamIn, ExamList, SubjectDetail, SubjectList, TopicDetail
from app.schemas.play import AnswerRequest, AnswerResult, PlayState, StartPlayRequest, Summary
from app.schemas.progress import DueReviews, Home, WeakSpots
from app.services import play, progress

router = APIRouter()


# --- catalogue ------------------------------------------------------------------------------


@router.get("/subjects", tags=["catalogue"])
async def list_subjects(_: CurrentUser, db: DbSession) -> SubjectList:
    return SubjectList(subjects=await progress.list_subjects(db))


@router.get("/subjects/{subject_id}", tags=["catalogue"])
async def get_subject(subject_id: int, user: CurrentUser, db: DbSession, now: Now) -> SubjectDetail:
    return await progress.subject_detail(db, user, subject_id, now)


@router.get("/topics/{topic_id}", tags=["catalogue"])
async def get_topic(
    topic_id: int,
    user: CurrentUser,
    db: DbSession,
    now: Now,
    subject_id: int | None = Query(default=None),
) -> TopicDetail:
    return await progress.topic_detail(db, user, topic_id, subject_id, now)


# --- play -----------------------------------------------------------------------------------


@router.post("/play", status_code=status.HTTP_201_CREATED, tags=["play"])
async def start_play(
    body: StartPlayRequest, user: CurrentUser, db: DbSession, now: Now
) -> PlayState:
    if body.mode == "review":
        return await play.start_review(db, user, now=now)
    assert body.topic_id is not None
    return await play.start_quiz(
        db,
        user,
        topic_id=body.topic_id,
        subject_id=body.subject_id,
        include_higher=body.include_higher,
        now=now,
    )


@router.get("/play/{session_id}", tags=["play"])
async def get_play(session_id: uuid.UUID, user: CurrentUser, db: DbSession) -> PlayState:
    return await play.get_state(db, user, session_id)


@router.post("/play/{session_id}/answer", tags=["play"])
async def answer(
    session_id: uuid.UUID, body: AnswerRequest, user: CurrentUser, db: DbSession, now: Now
) -> AnswerResult:
    return await play.answer(
        db, user, session_id, position=body.position, response=body.response, now=now
    )


@router.post("/play/{session_id}/end", tags=["play"])
async def end_play(session_id: uuid.UUID, user: CurrentUser, db: DbSession, now: Now) -> Summary:
    return await play.end_early(db, user, session_id, now=now)


# --- progress -------------------------------------------------------------------------------


@router.get("/home", tags=["progress"])
async def get_home(user: CurrentUser, db: DbSession, now: Now) -> Home:
    return await progress.home(db, user, now)


@router.get("/progress/weak-spots", tags=["progress"])
async def get_weak_spots(user: CurrentUser, db: DbSession, now: Now) -> WeakSpots:
    return await progress.weak_spots(db, user, now)


@router.get("/reviews/summary", tags=["progress"])
async def get_review_summary(user: CurrentUser, db: DbSession, now: Now) -> DueReviews:
    return await progress.due_reviews(db, user, now)


# --- exams ----------------------------------------------------------------------------------


@router.get("/exams", tags=["exams"])
async def list_exams(user: CurrentUser, db: DbSession, now: Now) -> ExamList:
    return ExamList(exams=await progress.list_exams(db, user, now))


@router.post("/exams", status_code=status.HTTP_201_CREATED, tags=["exams"])
async def add_exam(body: ExamIn, user: CurrentUser, db: DbSession, now: Now) -> Exam:
    return await progress.add_exam(db, user, body, now)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["exams"])
async def delete_exam(exam_id: int, user: CurrentUser, db: DbSession) -> None:
    await progress.delete_exam(db, user, exam_id)
