"""Importing this package registers every table on Base.metadata (Alembic relies on it)."""

from app.models.accounts import AuthSession, RateLimitHit, User
from app.models.base import Base
from app.models.content import (
    GenerationJob,
    Question,
    QuestionReport,
    QuestionSet,
    SetMember,
    Subject,
    SubjectTopic,
    Topic,
)
from app.models.play import ExamDate, PlaySession, QuestionReview, SessionAnswer, TopicProgress
from app.models.rewards import (
    Cosmetic,
    LeagueGroup,
    LeagueMember,
    LeagueWeek,
    UserCosmetic,
    UserEquipped,
    XpEvent,
)

__all__ = [
    "AuthSession",
    "Base",
    "Cosmetic",
    "ExamDate",
    "GenerationJob",
    "LeagueGroup",
    "LeagueMember",
    "LeagueWeek",
    "PlaySession",
    "Question",
    "QuestionReport",
    "QuestionReview",
    "QuestionSet",
    "RateLimitHit",
    "SessionAnswer",
    "SetMember",
    "Subject",
    "SubjectTopic",
    "Topic",
    "TopicProgress",
    "User",
    "UserCosmetic",
    "UserEquipped",
    "XpEvent",
]
