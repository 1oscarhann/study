from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.catalog import Exam


class TopicRefWithSubject(BaseModel):
    topic_id: int
    subject_id: int | None
    name: str
    subject_name: str | None


class WeakSpot(TopicRefWithSubject):
    answered: int
    correct: int
    accuracy: float
    enough_data: bool
    last_played_at: datetime | None


class WeakSpots(BaseModel):
    window_days: int
    min_answers: int
    topics: list[WeakSpot]


class DueReviews(BaseModel):
    today: int
    this_week: int


class RecentTopic(TopicRefWithSubject):
    accuracy: float | None
    last_played_at: datetime


class HomeUser(BaseModel):
    username: str
    year_group: int | None
    graduated: bool
    total_xp: int
    streak_current: int


class Home(BaseModel):
    user: HomeUser
    due_reviews: DueReviews
    recent_topics: list[RecentTopic]
    weakest_topic: WeakSpot | None
    exams: list[Exam]
