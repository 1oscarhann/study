"""XP ledger, cosmetics, equipped avatar, weekly leagues."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, text_enum
from app.models.enums import CosmeticSlot, LeagueOutcome, UnlockType, XpSource


class XpEvent(Base):
    __tablename__ = "xp_events"
    __table_args__ = (sa.Index("ix_xp_events_user_time", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(sa.Integer)
    source: Mapped[XpSource] = mapped_column(text_enum(XpSource, "xp_source"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("play_sessions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class Cosmetic(Base):
    __tablename__ = "cosmetics"
    __table_args__ = (
        # Lets user_equipped enforce "the item fits the slot" with a composite FK.
        sa.UniqueConstraint("id", "slot"),
        sa.CheckConstraint(
            "unlock_type NOT IN ('level', 'streak') OR unlock_value IS NOT NULL",
            name="unlock_value_required",
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    key: Mapped[str] = mapped_column(sa.String(64), unique=True)  # asset filename stem
    slot: Mapped[CosmeticSlot] = mapped_column(text_enum(CosmeticSlot, "cosmetic_slot"))
    name: Mapped[str] = mapped_column(sa.String(60))
    unlock_type: Mapped[UnlockType] = mapped_column(text_enum(UnlockType, "unlock_type"))
    unlock_value: Mapped[int | None] = mapped_column(sa.Integer)  # level N or streak N days
    sort_order: Mapped[int] = mapped_column(sa.Integer, server_default="0")


class UserCosmetic(Base):
    __tablename__ = "user_cosmetics"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    cosmetic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cosmetics.id", ondelete="CASCADE"), primary_key=True
    )
    unlocked_at: Mapped[datetime] = created_at_col()


class UserEquipped(Base):
    """You can only equip something you own, in the slot it belongs to (both DB-enforced)."""

    __tablename__ = "user_equipped"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "cosmetic_id"],
            ["user_cosmetics.user_id", "user_cosmetics.cosmetic_id"],
            ondelete="CASCADE",
            name="fk_user_equipped_owned",
        ),
        sa.ForeignKeyConstraint(
            ["cosmetic_id", "slot"],
            ["cosmetics.id", "cosmetics.slot"],
            ondelete="CASCADE",
            name="fk_user_equipped_slot_matches",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    slot: Mapped[CosmeticSlot] = mapped_column(
        text_enum(CosmeticSlot, "equipped_slot"), primary_key=True
    )
    cosmetic_id: Mapped[int] = mapped_column(sa.BigInteger)


class LeagueWeek(Base):
    __tablename__ = "league_weeks"

    week_start: Mapped[date] = mapped_column(sa.Date, primary_key=True)  # Monday, UK time
    settled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class LeagueGroup(Base):
    __tablename__ = "league_groups"
    __table_args__ = (
        sa.CheckConstraint("tier BETWEEN 0 AND 4", name="tier_range"),
        sa.CheckConstraint("year_group BETWEEN 7 AND 13", name="year_group_range"),
        sa.Index("ix_league_groups_lookup", "week_start", "tier", "year_group"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    week_start: Mapped[date] = mapped_column(
        sa.ForeignKey("league_weeks.week_start", ondelete="CASCADE")
    )
    tier: Mapped[int] = mapped_column(sa.SmallInteger)
    year_group: Mapped[int] = mapped_column(sa.SmallInteger)
    created_at: Mapped[datetime] = created_at_col()


class LeagueMember(Base):
    __tablename__ = "league_members"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "week_start"),
        sa.Index("ix_league_members_group_xp", "group_id", sa.text("weekly_xp DESC")),
    )

    group_id: Mapped[int] = mapped_column(
        sa.ForeignKey("league_groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    week_start: Mapped[date] = mapped_column(sa.Date)  # denormalised for the unique check
    weekly_xp: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    last_xp_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))  # tiebreak
    outcome: Mapped[LeagueOutcome | None] = mapped_column(
        text_enum(LeagueOutcome, "league_outcome")
    )
