from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import Auth, CurrentUser, Limiter, Now, SettingsDep
from app.db import DbSession
from app.schemas.accounts import (
    ChangePasswordRequest,
    MeResponse,
    PasswordConfirmRequest,
    RecoveryCodeResponse,
    YearGroupRequest,
)
from app.security.sessions import clear_session_cookie
from app.services import accounts

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
async def get_me(user: CurrentUser, now: Now) -> MeResponse:
    return accounts.me_response(user, now)


@router.patch("/year-group")
async def change_year_group(
    body: YearGroupRequest, user: CurrentUser, db: DbSession, now: Now
) -> MeResponse:
    user = await accounts.change_year_group(db, user, year_group=body.year_group, now=now)
    return accounts.me_response(user, now)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest, auth: Auth, db: DbSession, limiter: Limiter, now: Now
) -> None:
    await accounts.change_password(
        db,
        limiter,
        auth.user,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_session_id=auth.session.id,
        now=now,
    )


@router.post("/recovery-code")
async def regenerate_recovery_code(
    body: PasswordConfirmRequest, user: CurrentUser, db: DbSession, limiter: Limiter, now: Now
) -> RecoveryCodeResponse:
    code = await accounts.regenerate_recovery_code(
        db, limiter, user, password=body.password, now=now
    )
    return RecoveryCodeResponse(recovery_code=code)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: PasswordConfirmRequest,
    user: CurrentUser,
    db: DbSession,
    limiter: Limiter,
    settings: SettingsDep,
    now: Now,
) -> Response:
    await accounts.delete_account(db, limiter, user, password=body.password, now=now)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings)
    return response
