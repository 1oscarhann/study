from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SubjectSummary(BaseModel):
    id: int
    slug: str
    name: str
    qualification: str
    exam_board: str
    topic_count: int
    playable_topic_count: int = Field(description="Topics with at least one live question")


class SubjectList(BaseModel):
    subjects: list[SubjectSummary]


class MyTopicStats(BaseModel):
    answered: int
    correct: int
    accuracy: float | None


class TopicSummary(BaseModel):
    topic_id: int
    slug: str
    name: str
    spec_ref: str | None
    question_count: int
    stats: MyTopicStats
    last_played_at: datetime | None


class SubjectDetail(BaseModel):
    id: int
    slug: str
    name: str
    qualification: str
    exam_board: str
    spec_code: str | None
    topics: list[TopicSummary]


class Subtopic(BaseModel):
    name: str
    higher_only: bool = False
    triple_only: bool = False


class TopicDetail(BaseModel):
    topic_id: int
    slug: str
    name: str
    subject_id: int | None
    subject_name: str | None
    spec_ref: str | None
    subtopics: list[Subtopic]
    learn_more_url: str | None
    question_count: int
    higher_only_count: int
    due_count: int
    stats: MyTopicStats
    last_played_at: datetime | None


class ExamIn(BaseModel):
    subject_id: int
    exam_date: date
    label: str | None = Field(default=None, max_length=40)


class Exam(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    label: str | None
    exam_date: date
    days_left: int


class ExamList(BaseModel):
    exams: list[Exam]
