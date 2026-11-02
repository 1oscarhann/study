from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.deps import ClientIp, Limiter, Now, SettingsDep
from app.db import DbSession
from app.schemas.accounts import (
    AuthResponse,
    AuthWithRecoveryCodeResponse,
    LoginRequest,
    RecoverRequest,
    SignupRequest,
    UsernameIdeasResponse,
)
from app.security import rate_limit as rl
from app.security.sessions import (
    clear_session_cookie,
    cookie_name,
    delete_session_by_token,
    set_session_cookie,
)
from app.services import accounts

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    response: Response,
    db: DbSession,
    limiter: Limiter,
    settings: SettingsDep,
    ip: ClientIp,
    now: Now,
) -> AuthWithRecoveryCodeResponse:
    result = await accounts.signup(
        db,
        limiter,
        ip=ip,
        username=body.username,
        password=body.password,
        year_group=body.year_group,
        now=now,
    )
    set_session_cookie(response, settings, result.token)
    assert result.recovery_code is not None
    return AuthWithRecoveryCodeResponse(
        user=accounts.me_response(result.user, now), recovery_code=result.recovery_code
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: DbSession,
    limiter: Limiter,
    settings: SettingsDep,
    ip: ClientIp,
    now: Now,
) -> AuthResponse:
    result = await accounts.login(
        db, limiter, ip=ip, username=body.username, password=body.password, now=now
    )
    set_session_cookie(response, settings, result.token)
    return AuthResponse(user=accounts.me_response(result.user, now))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, db: DbSession, settings: SettingsDep) -> Response:
    token = request.cookies.get(cookie_name(settings))
    if token:
        await delete_session_by_token(db, token)
        await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings)
    return response


@router.post("/recover")
async def recover(
    body: RecoverRequest,
    response: Response,
    db: DbSession,
    limiter: Limiter,
    settings: SettingsDep,
    ip: ClientIp,
    now: Now,
) -> AuthWithRecoveryCodeResponse:
    result = await accounts.recover(
        db,
        limiter,
        ip=ip,
        username=body.username,
        recovery_code=body.recovery_code,
        new_password=body.new_password,
        now=now,
    )
    set_session_cookie(response, settings, result.token)
    assert result.recovery_code is not None
    return AuthWithRecoveryCodeResponse(
        user=accounts.me_response(result.user, now), recovery_code=result.recovery_code
    )


@router.get("/username-ideas")
async def username_ideas(
    db: DbSession, limiter: Limiter, ip: ClientIp, now: Now
) -> UsernameIdeasResponse:
    await limiter.consume(rl.USERNAME_IDEAS_PER_IP, limiter.ip_subject(ip), now)
    return UsernameIdeasResponse(ideas=await accounts.available_username_ideas(db))
