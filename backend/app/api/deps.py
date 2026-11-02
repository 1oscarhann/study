"""Shared FastAPI dependencies: settings, clock, client IP, rate limiter, current user."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request, Response

from app.config import Settings
from app.db import DbSession
from app.domain.calendar import utc_now
from app.errors import AppError
from app.models import AuthSession, User
from app.security.proxy import client_ip
from app.security.rate_limit import RateLimiter
from app.security.sessions import cookie_name, resolve_session, set_session_cookie


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_now() -> datetime:
    """The current time. Tests override this to time-travel (e.g. across 1 September)."""
    return utc_now()


def get_client_ip(request: Request) -> str:
    return client_ip(request)


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
Now = Annotated[datetime, Depends(get_now)]
ClientIp = Annotated[str, Depends(get_client_ip)]
Limiter = Annotated[RateLimiter, Depends(get_limiter)]


class AuthContext:
    def __init__(self, user: User, session: AuthSession) -> None:
        self.user = user
        self.session = session


async def get_auth(
    request: Request, response: Response, db: DbSession, settings: SettingsDep, now: Now
) -> AuthContext:
    token = request.cookies.get(cookie_name(settings))
    resolved = await resolve_session(db, token, now) if token else None
    if resolved is None:
        raise AppError(401, "Please log in.", code="not_authenticated")
    if resolved.refreshed and token:
        set_session_cookie(response, settings, token)  # slide the cookie's expiry too
    return AuthContext(resolved.user, resolved.session)


Auth = Annotated[AuthContext, Depends(get_auth)]


async def get_current_user(auth: Auth) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]
