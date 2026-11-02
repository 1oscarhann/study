"""Subjects, topics, questions, user sets, AI generation jobs, reports.

Topics can belong to more than one subject: AQA Combined Science reuses the separate
sciences' topics (e.g. `sci-bio-cells`), so one question bank serves both. The link
row (`subject_topics`) carries the per-subject display name and spec ref, and whether
triple-only content is excluded when playing through that subject.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, text_enum, updated_at_col
from app.models.enums import (
    BoardConfidence,
    GenerationStatus,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    ReportReason,
    ReportStatus,
    VerificationStatus,
)

SLUG_PATTERN = "'^[a-z0-9]+(-[a-z0-9]+)*$'"


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (sa.CheckConstraint(f"slug ~ {SLUG_PATTERN}", name="slug_format"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(sa.String(80), unique=True)
    name: Mapped[str] = mapped_column(sa.String(120))
    qualification: Mapped[str] = mapped_column(sa.String(80))  # "GCSE", "GCSE (triple)", …
    exam_board: Mapped[str] = mapped_column(sa.String(80))  # free text: "AQA", "Eduqas", …
    spec_code: Mapped[str | None] = mapped_column(sa.String(120))
    spec_url: Mapped[str | None] = mapped_column(sa.Text)
    spec_url_alt: Mapped[str | None] = mapped_column(sa.Text)
    board_confidence: Mapped[BoardConfidence] = mapped_column(
        text_enum(BoardConfidence, "board_confidence"), server_default=BoardConfidence.STATED
    )
    admin_notes: Mapped[str | None] = mapped_column(sa.Text)
    sort_order: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.true())
    created_at: Mapped[datetime] = created_at_col()


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        sa.CheckConstraint(f"slug ~ {SLUG_PATTERN}", name="slug_format"),
        sa.CheckConstraint(
            "learn_more_url IS NULL OR learn_more_url LIKE 'https://%'",
            name="learn_more_url_https",
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(sa.String(80), unique=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    # [{"name": str, "higher_only": bool, "triple_only": bool}, ...] — also grounds the AI.
    subtopics: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sa.text("'[]'::jsonb")
    )
    learn_more_url: Mapped[str | None] = mapped_column(sa.Text)
    boss_cosmetic_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("cosmetics.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.true())
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class SubjectTopic(Base):
    __tablename__ = "subject_topics"

    subject_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    display_name: Mapped[str] = mapped_column(sa.String(200))
    spec_ref: Mapped[str | None] = mapped_column(sa.String(40))
    sort_order: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    # True for Combined Science links: hide questions tagged triple_only.
    excludes_triple_only: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())


class QuestionSet(Base):
    """A user-made set. Official questions don't live in sets (questions.set_id IS NULL)."""

    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    owner_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(sa.ForeignKey("topics.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(sa.String(80))
    join_code: Mapped[str | None] = mapped_column(sa.String(12), unique=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class SetMember(Base):
    __tablename__ = "set_members"

    set_id: Mapped[int] = mapped_column(
        sa.ForeignKey("question_sets.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = created_at_col()


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    set_id: Mapped[int] = mapped_column(sa.ForeignKey("question_sets.id", ondelete="CASCADE"))
    status: Mapped[GenerationStatus] = mapped_column(
        text_enum(GenerationStatus, "generation_status"), server_default=GenerationStatus.QUEUED
    )
    # The pasted notes. Purged once every draft is reviewed, or after 7 days.
    notes: Mapped[str | None] = mapped_column(sa.Text)
    notes_purged_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    requested_count: Mapped[int] = mapped_column(sa.SmallInteger)
    requested_types: Mapped[list[str]] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(sa.String(64))
    input_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    output_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    error: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = created_at_col()
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        # The core accuracy rule: AI-generated questions can't go live without approval.
        sa.CheckConstraint(
            "NOT (origin = 'ai' AND status = 'live' AND approved_at IS NULL)",
            name="ai_live_requires_approval",
        ),
        sa.CheckConstraint("char_length(explanation) BETWEEN 1 AND 200", name="explanation_len"),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 3", name="difficulty_range"),
        sa.CheckConstraint("NOT (is_core AND set_id IS NOT NULL)", name="core_is_official_only"),
        sa.CheckConstraint("report_count >= 0", name="report_count_non_negative"),
        sa.Index(
            "ix_questions_official_topic_status",
            "topic_id",
            "status",
            postgresql_where=sa.text("set_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    topic_id: Mapped[int] = mapped_column(sa.ForeignKey("topics.id", ondelete="RESTRICT"))
    # NULL = official question bank.
    set_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("question_sets.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[QuestionType] = mapped_column(text_enum(QuestionType, "question_type"))
    prompt: Mapped[str] = mapped_column(sa.Text)
    # What the player sees (options / items / pairs). Validated per type in app code.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Server-only. Never serialised to a client before they've answered.
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(sa.String(200))
    subtopic: Mapped[str | None] = mapped_column(sa.String(200))
    difficulty: Mapped[int] = mapped_column(sa.SmallInteger, server_default="2")
    is_core: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    higher_only: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    triple_only: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    case_sensitive: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    status: Mapped[QuestionStatus] = mapped_column(
        text_enum(QuestionStatus, "question_status"), server_default=QuestionStatus.DRAFT
    )
    origin: Mapped[QuestionOrigin] = mapped_column(text_enum(QuestionOrigin, "question_origin"))
    verification: Mapped[VerificationStatus] = mapped_column(
        text_enum(VerificationStatus, "verification_status"),
        server_default=VerificationStatus.UNCHECKED,
    )
    verification_note: Mapped[str | None] = mapped_column(sa.Text)
    source_quote: Mapped[str | None] = mapped_column(sa.Text)
    human_edited: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    report_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("generation_jobs.id", ondelete="SET NULL")
    )
    created_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class QuestionReport(Base):
    __tablename__ = "question_reports"
    __table_args__ = (sa.UniqueConstraint("question_id", "reporter_id"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    question_id: Mapped[int] = mapped_column(
        sa.ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    # Set to NULL if the reporter deletes their account; the report itself stays.
    reporter_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[ReportReason] = mapped_column(text_enum(ReportReason, "report_reason"))
    comment: Mapped[str | None] = mapped_column(sa.String(300))
    status: Mapped[ReportStatus] = mapped_column(
        text_enum(ReportStatus, "report_status"), server_default=ReportStatus.OPEN
    )
    resolved_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
