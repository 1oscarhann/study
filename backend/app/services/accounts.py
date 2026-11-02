"""Signup, login, recovery and account settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.calendar import academic_year_start, uk_today
from app.domain.year_group import can_correct, cohort_for, status_for
from app.errors import AppError
from app.models import User
from app.schemas.accounts import MeResponse
from app.security import rate_limit as rl
from app.security.passwords import (
    burn_verify_time,
    hash_secret,
    needs_rehash,
    new_recovery_code,
    normalise_recovery_code,
    password_problem,
    verify_secret,
)
from app.security.rate_limit import RateLimiter
from app.security.sessions import create_session, delete_user_sessions
from app.security.usernames import USERNAME_RE, username_ideas, username_problem

BAD_LOGIN = "Wrong username or password."
BAD_RECOVERY = "That username and recovery code don't match."


def me_response(user: User, now: datetime) -> MeResponse:
    today = uk_today(now)
    status = status_for(user.cohort_year, today)
    return MeResponse(
        username=user.username,
        year_group=status.year_group,
        graduated=status.graduated,
        can_change_year_group=can_correct(user.year_group_changed_for, today),
        is_admin=user.is_admin,
        total_xp=user.total_xp,
        league_tier=user.league_tier,
        streak_current=user.streak_current,
        created_at=user.created_at,
    )


async def find_user(db: AsyncSession, username: str) -> User | None:
    if not USERNAME_RE.fullmatch(username):
        return None
    return await db.scalar(select(User).where(func.lower(User.username) == username.lower()))


def _check_new_password(password: str, username: str, field: str) -> None:
    if problem := password_problem(password, username):
        raise AppError(422, problem, code="weak_password", field=field)


@dataclass
class LoggedIn:
    user: User
    token: str
    recovery_code: str | None = None


async def signup(
    db: AsyncSession,
    limiter: RateLimiter,
    *,
    ip: str,
    username: str,
    password: str,
    year_group: int,
    now: datetime,
) -> LoggedIn:
    await limiter.consume(rl.SIGNUP_PER_IP, limiter.ip_subject(ip), now)
    username = username.strip()
    if problem := username_problem(username):
        raise AppError(422, problem, code="bad_username", field="username")
    _check_new_password(password, username, "password")
    if await find_user(db, username):
        raise AppError(409, "That username's taken. Try another.", code="username_taken",
                       field="username")  # fmt: skip

    recovery_code = new_recovery_code()
    user = User(
        username=username,
        password_hash=await hash_secret(password),
        recovery_code_hash=await hash_secret(normalise_recovery_code(recovery_code)),
        cohort_year=cohort_for(year_group, uk_today(now)),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # two people grabbed the same name at once
        await db.rollback()
        raise AppError(409, "That username's taken. Try another.", code="username_taken",
                       field="username") from exc  # fmt: skip
    token = await create_session(db, user.id, now)
    await db.commit()
    await db.refresh(user)
    return LoggedIn(user, token, recovery_code)


async def login(
    db: AsyncSession,
    limiter: RateLimiter,
    *,
    ip: str,
    username: str,
    password: str,
    now: datetime,
) -> LoggedIn:
    username = username.strip()
    await limiter.consume(rl.LOGIN_PER_IP, limiter.ip_subject(ip), now)
    await limiter.ensure_under(rl.LOGIN_FAILURES_PER_USERNAME, username.lower(), now)

    user = await find_user(db, username)
    if user is None:
        await burn_verify_time(password)
        ok = False
    else:
        ok = await verify_secret(user.password_hash, password)
    if not ok or user is None:
        await limiter.hit(rl.LOGIN_FAILURES_PER_USERNAME, username.lower(), now)
        raise AppError(401, BAD_LOGIN, code="bad_credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = await hash_secret(password)
    token = await create_session(db, user.id, now)
    await db.commit()
    return LoggedIn(user, token)


async def recover(
    db: AsyncSession,
    limiter: RateLimiter,
    *,
    ip: str,
    username: str,
    recovery_code: str,
    new_password: str,
    now: datetime,
) -> LoggedIn:
    username = username.strip()
    await limiter.consume(rl.RECOVER_PER_IP, limiter.ip_subject(ip), now)
    # Cheap checks first, so a weak new password doesn't burn a recovery attempt.
    _check_new_password(new_password, username, "new_password")
    await limiter.consume(rl.RECOVER_PER_USERNAME, username.lower(), now)

    code = normalise_recovery_code(recovery_code)
    user = await find_user(db, username)
    if user is None:
        await burn_verify_time(code)
        raise AppError(401, BAD_RECOVERY, code="bad_recovery_code")
    if not await verify_secret(user.recovery_code_hash, code):
        raise AppError(401, BAD_RECOVERY, code="bad_recovery_code")

    new_code = new_recovery_code()
    user.password_hash = await hash_secret(new_password)
    user.recovery_code_hash = await hash_secret(normalise_recovery_code(new_code))
    await delete_user_sessions(db, user.id)  # log out everywhere
    token = await create_session(db, user.id, now)
    await db.commit()
    return LoggedIn(user, token, new_code)


async def _require_password(
    limiter: RateLimiter, user: User, password: str, now: datetime, field: str
) -> None:
    await limiter.consume(rl.PASSWORD_CHECKS_PER_USER, str(user.id), now)
    if not await verify_secret(user.password_hash, password):
        raise AppError(401, "That password isn't right.", code="bad_password", field=field)


async def change_year_group(
    db: AsyncSession, user: User, *, year_group: int, now: datetime
) -> User:
    today = uk_today(now)
    current = status_for(user.cohort_year, today)
    if not current.graduated and current.year_group == year_group:
        return user  # no change, so it doesn't use up the yearly correction
    if not can_correct(user.year_group_changed_for, today):
        raise AppError(
            409,
            "You've already changed your year group this school year. "
            "You can change it again from 1 September.",
            code="year_group_locked",
            field="year_group",
        )
    user.cohort_year = cohort_for(year_group, today)
    user.year_group_changed_for = academic_year_start(today)
    await db.commit()
    return user


async def change_password(
    db: AsyncSession,
    limiter: RateLimiter,
    user: User,
    *,
    current_password: str,
    new_password: str,
    keep_session_id: int,
    now: datetime,
) -> None:
    await _require_password(limiter, user, current_password, now, "current_password")
    _check_new_password(new_password, user.username, "new_password")
    user.password_hash = await hash_secret(new_password)
    await delete_user_sessions(db, user.id, keep_session_id=keep_session_id)
    await db.commit()


async def regenerate_recovery_code(
    db: AsyncSession, limiter: RateLimiter, user: User, *, password: str, now: datetime
) -> str:
    await _require_password(limiter, user, password, now, "password")
    code = new_recovery_code()
    user.recovery_code_hash = await hash_secret(normalise_recovery_code(code))
    await db.commit()
    return code


async def delete_account(
    db: AsyncSession, limiter: RateLimiter, user: User, *, password: str, now: datetime
) -> None:
    await _require_password(limiter, user, password, now, "password")
    # FKs cascade: sessions, answers, sets, XP, leagues… Reports they filed are kept,
    # with the reporter set to NULL.
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()


async def available_username_ideas(db: AsyncSession, count: int = 5) -> list[str]:
    candidates = username_ideas(count * 3)
    taken = set(
        (
            await db.scalars(
                select(func.lower(User.username)).where(
                    func.lower(User.username).in_([c.lower() for c in candidates])
                )
            )
        ).all()
    )
    return [c for c in candidates if c.lower() not in taken][:count]
