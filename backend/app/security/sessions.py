"""Server-side sessions in an httpOnly cookie.

The browser holds a random token; the DB holds only its SHA-256. Sessions last 30 days
from last use (refreshed at most once a day) and can be revoked instantly.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AuthSession, User

SESSION_TTL = timedelta(days=30)
REFRESH_AFTER = timedelta(days=1)


def cookie_name(settings: Settings) -> str:
    # The __Host- prefix makes browsers insist on Secure, Path=/ and no Domain, so the
    # cookie can't be set or overwritten by any other (sub)domain. It needs HTTPS, so
    # local dev/tests over http use a plain name.
    return "__Host-rb_session" if settings.cookie_secure else "rb_session"


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        cookie_name(settings),
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        cookie_name(settings),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


async def create_session(db: AsyncSession, user_id: int, now: datetime) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=now + SESSION_TTL,
            last_seen_at=now,
        )
    )
    return token


@dataclass
class ResolvedSession:
    session: AuthSession
    user: User
    refreshed: bool


async def resolve_session(db: AsyncSession, token: str, now: datetime) -> ResolvedSession | None:
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == hash_token(token), AuthSession.expires_at > now)
        )
    ).first()
    if row is None:
        return None
    session, user = row
    refreshed = False
    if now - session.last_seen_at >= REFRESH_AFTER:
        await db.execute(
            update(AuthSession)
            .where(AuthSession.id == session.id)
            .values(last_seen_at=now, expires_at=now + SESSION_TTL)
        )
        await db.commit()
        refreshed = True
    return ResolvedSession(session=session, user=user, refreshed=refreshed)


async def delete_session_by_token(db: AsyncSession, token: str) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))


async def delete_user_sessions(
    db: AsyncSession, user_id: int, *, keep_session_id: int | None = None
) -> None:
    stmt = delete(AuthSession).where(AuthSession.user_id == user_id)
    if keep_session_id is not None:
        stmt = stmt.where(AuthSession.id != keep_session_id)
    await db.execute(stmt)
