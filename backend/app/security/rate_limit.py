"""Fixed-window rate limits stored in Postgres (survive restarts, work across instances).

Each hit is committed in its own short transaction, so failed attempts still count even
when the request itself errors and rolls back. IP addresses are only ever stored as an
HMAC, never raw.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError
from app.models import RateLimitHit


@dataclass(frozen=True)
class Limit:
    name: str
    max_hits: int
    window: timedelta


# School Wi-Fi often puts a whole school behind one IP, so per-IP limits are generous and
# the strict limits are per username / per account.
LOGIN_PER_IP = Limit("login-ip", 100, timedelta(minutes=15))
LOGIN_FAILURES_PER_USERNAME = Limit("login-fail-user", 10, timedelta(minutes=15))
SIGNUP_PER_IP = Limit("signup-ip", 30, timedelta(hours=1))
RECOVER_PER_IP = Limit("recover-ip", 30, timedelta(hours=1))
RECOVER_PER_USERNAME = Limit("recover-user", 5, timedelta(hours=1))
PASSWORD_CHECKS_PER_USER = Limit("password-user", 10, timedelta(hours=1))
USERNAME_IDEAS_PER_IP = Limit("ideas-ip", 120, timedelta(hours=1))

_PURGE_AFTER = timedelta(days=2)


class RateLimited(AppError):
    def __init__(self, retry_after_seconds: int) -> None:
        minutes = max(1, math.ceil(retry_after_seconds / 60))
        unit = "minute" if minutes == 1 else "minutes"
        super().__init__(
            429,
            f"Too many attempts. Try again in {minutes} {unit}.",
            code="rate_limited",
            headers={"Retry-After": str(retry_after_seconds)},
        )


def _window_start(now: datetime, window: timedelta) -> datetime:
    seconds = int(window.total_seconds())
    return datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, UTC)


class RateLimiter:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], secret_key: str) -> None:
        self._sessionmaker = sessionmaker
        self._secret = secret_key.encode()

    def ip_subject(self, ip: str) -> str:
        return hmac.new(self._secret, ip.encode(), hashlib.sha256).hexdigest()[:32]

    @staticmethod
    def _key(limit: Limit, subject: str) -> str:
        return f"{limit.name}:{subject[:64]}"

    async def hit(self, limit: Limit, subject: str, now: datetime) -> int:
        """Record one hit and return the count in the current window."""
        start = _window_start(now, limit.window)
        stmt = (
            insert(RateLimitHit)
            .values(key=self._key(limit, subject), window_start=start, count=1)
            .on_conflict_do_update(
                index_elements=[RateLimitHit.key, RateLimitHit.window_start],
                set_={"count": RateLimitHit.count + 1},
            )
            .returning(RateLimitHit.count)
        )
        async with self._sessionmaker() as session:
            count = (await session.execute(stmt)).scalar_one()
            if secrets.randbelow(200) == 0:  # occasional cleanup of old windows
                await session.execute(
                    delete(RateLimitHit).where(RateLimitHit.window_start < now - _PURGE_AFTER)
                )
            await session.commit()
        return count

    async def count(self, limit: Limit, subject: str, now: datetime) -> int:
        start = _window_start(now, limit.window)
        async with self._sessionmaker() as session:
            value = await session.scalar(
                select(RateLimitHit.count).where(
                    RateLimitHit.key == self._key(limit, subject),
                    RateLimitHit.window_start == start,
                )
            )
        return value or 0

    @staticmethod
    def _retry_after(limit: Limit, now: datetime) -> int:
        end = _window_start(now, limit.window) + limit.window
        return max(1, math.ceil((end - now).total_seconds()))

    async def consume(self, limit: Limit, subject: str, now: datetime) -> None:
        """Count this attempt; refuse it if it goes over the limit."""
        if await self.hit(limit, subject, now) > limit.max_hits:
            raise RateLimited(self._retry_after(limit, now))

    async def ensure_under(self, limit: Limit, subject: str, now: datetime) -> None:
        """Refuse if the limit is already used up, without counting this attempt."""
        if await self.count(limit, subject, now) >= limit.max_hits:
            raise RateLimited(self._retry_after(limit, now))
