"""Play sessions, the answer log, spaced-repetition state, per-topic progress, exam dates."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, text_enum
from app.models.enums import PlayMode, SessionResult, SessionStatus


class PlaySession(Base):
    __tablename__ = "play_sessions"
    __table_args__ = (sa.Index("ix_play_sessions_user_started", "user_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"))
    mode: Mapped[PlayMode] = mapped_column(text_enum(PlayMode, "play_mode"))
    # Subject context matters: playing via Combined Science hides triple-only questions.
    subject_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("subjects.id", ondelete="SET NULL")
    )
    topic_id: Mapped[int | None] = mapped_column(sa.ForeignKey("topics.id", ondelete="SET NULL"))
    set_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("question_sets.id", ondelete="SET NULL")
    )
    include_higher: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.true())
    status: Mapped[SessionStatus] = mapped_column(
        text_enum(SessionStatus, "session_status"), server_default=SessionStatus.ACTIVE
    )
    question_count: Mapped[int] = mapped_column(sa.SmallInteger)
    current_position: Mapped[int] = mapped_column(sa.SmallInteger, server_default="0")
    user_score: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    bot_score: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    bot_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # name, accuracy, seed
    boss_hp: Mapped[int | None] = mapped_column(sa.Integer)
    hearts: Mapped[int | None] = mapped_column(sa.SmallInteger)
    result: Mapped[SessionResult | None] = mapped_column(text_enum(SessionResult, "session_result"))
    xp_awarded: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    started_at: Mapped[datetime] = created_at_col()
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SessionAnswer(Base):
    """One row per question served in a session. Also the answer log behind all stats."""

    __tablename__ = "session_answers"
    __table_args__ = (
        sa.Index("ix_session_answers_user_topic_time", "user_id", "topic_id", "answered_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("play_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        sa.ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(sa.ForeignKey("topics.id", ondelete="RESTRICT"))
    shown: Mapped[dict[str, Any]] = mapped_column(JSONB)  # shuffled order the player saw
    served_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_correct: Mapped[bool | None] = mapped_column(sa.Boolean)
    response_ms: Mapped[int | None] = mapped_column(sa.Integer)
    points: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    bot_correct: Mapped[bool | None] = mapped_column(sa.Boolean)
    bot_ms: Mapped[int | None] = mapped_column(sa.Integer)
    bot_points: Mapped[int | None] = mapped_column(sa.Integer)


class QuestionReview(Base):
    """Leitner box state per user per question."""

    __tablename__ = "question_reviews"
    __table_args__ = (
        sa.CheckConstraint("box BETWEEN 1 AND 5", name="box_range"),
        sa.Index("ix_question_reviews_user_due", "user_id", "due_on"),
    )

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        sa.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    box: Mapped[int] = mapped_column(sa.SmallInteger)
    due_on: Mapped[date] = mapped_column(sa.Date)  # UK calendar date
    times_right: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    times_wrong: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )


class TopicProgress(Base):
    __tablename__ = "topic_progress"
    __table_args__ = (sa.Index("ix_topic_progress_user_played", "user_id", "last_played_at"),)

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    last_played_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    boss_unlocked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    boss_defeated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class ExamDate(Base):
    __tablename__ = "exam_dates"
    __table_args__ = (sa.Index("ix_exam_dates_user_date", "user_id", "exam_date"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(sa.ForeignKey("subjects.id", ondelete="CASCADE"))
    label: Mapped[str | None] = mapped_column(sa.String(40))  # e.g. "Paper 1"
    exam_date: Mapped[date] = mapped_column(sa.Date)
    created_at: Mapped[datetime] = created_at_col()
