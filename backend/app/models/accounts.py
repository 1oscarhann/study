"""Users, auth sessions, rate-limit counters.

`users` is deliberately tiny: username, password hash, recovery-code hash, year-group
cohort, plus game state. No email, real name, school, DOB or anything else, ever.
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.CheckConstraint("username ~ '^[A-Za-z0-9_]{3,20}$'", name="username_format"),
        sa.CheckConstraint("total_xp >= 0", name="total_xp_non_negative"),
        sa.CheckConstraint("league_tier BETWEEN 0 AND 4", name="league_tier_range"),
        sa.CheckConstraint("streak_freezes BETWEEN 0 AND 1", name="streak_freezes_range"),
        sa.Index("uq_users_username_lower", sa.func.lower(sa.text("username")), unique=True),
        sa.Index("ix_users_cohort_xp", "cohort_year", sa.text("total_xp DESC")),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(20))
    password_hash: Mapped[str] = mapped_column(sa.Text)
    recovery_code_hash: Mapped[str] = mapped_column(sa.Text)
    # Calendar year of the September this user started (or would have started) Year 7.
    cohort_year: Mapped[int] = mapped_column(sa.SmallInteger)
    # Academic year (its starting calendar year) in which they last corrected their year group.
    year_group_changed_for: Mapped[int | None] = mapped_column(sa.SmallInteger)
    is_admin: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())

    total_xp: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    league_tier: Mapped[int] = mapped_column(sa.SmallInteger, server_default="0")
    streak_current: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    streak_best: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    streak_last_day: Mapped[date | None] = mapped_column(sa.Date)
    streak_freezes: Mapped[int] = mapped_column(sa.SmallInteger, server_default="0")
    streak_freeze_week: Mapped[date | None] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = created_at_col()


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # SHA-256 of the cookie token. The raw token is never stored.
    token_hash: Mapped[bytes] = mapped_column(sa.LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class RateLimitHit(Base):
    """Fixed-window counters. Keys hold usernames or HMAC'd IPs, never raw IPs."""

    __tablename__ = "rate_limit_hits"

    key: Mapped[str] = mapped_column(sa.String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
