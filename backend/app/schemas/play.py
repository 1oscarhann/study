from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import PlayMode, QuestionType, SessionStatus


class StartPlayRequest(BaseModel):
    mode: Literal["quiz", "review"]
    topic_id: int | None = None
    subject_id: int | None = None
    include_higher: bool = True

    @model_validator(mode="after")
    def _topic_for_quiz(self) -> StartPlayRequest:
        if self.mode == "quiz" and self.topic_id is None:
            raise ValueError("A quick quiz needs a topic_id.")
        return self


class Choice(BaseModel):
    id: str
    text: str


class ServedQuestion(BaseModel):
    """What the player sees. Never contains the answer."""

    position: int
    question_id: int
    type: QuestionType
    prompt: str
    subtopic: str | None
    topic_name: str
    options: list[Choice] | None = None  # mcq
    items: list[Choice] | None = None  # order
    left: list[Choice] | None = None  # match: terms
    right: list[Choice] | None = None  # match: definitions


class Progress(BaseModel):
    answered: int
    correct: int
    total: int


class TopicRef(BaseModel):
    id: int
    name: str


class ResultRow(BaseModel):
    position: int
    prompt: str
    correct: bool | None


class Summary(BaseModel):
    mode: PlayMode
    status: SessionStatus
    topic: TopicRef | None
    subject_id: int | None
    total: int
    answered: int
    correct: int
    accuracy: float | None
    results: list[ResultRow]
    xp_awarded: int


class PlayState(BaseModel):
    session_id: uuid.UUID
    mode: PlayMode
    status: SessionStatus
    topic: TopicRef | None
    subject_id: int | None
    progress: Progress
    question: ServedQuestion | None
    summary: Summary | None


class AnswerRequest(BaseModel):
    position: int = Field(ge=0, le=100)
    response: dict[str, Any]


class ReviewInfo(BaseModel):
    box: int
    due_on: date
    days_until_due: int


class Feedback(BaseModel):
    position: int
    correct: bool
    partial: str | None
    correct_answer: dict[str, Any]
    your_response: dict[str, Any]
    explanation: str
    learn_more_url: str | None  # only after a wrong answer
    review: ReviewInfo | None


class AnswerResult(BaseModel):
    feedback: Feedback
    progress: Progress
    next: ServedQuestion | None
    summary: Summary | None
