"""Request/response models for auth and account settings.

Request fields only get coarse limits here; the friendly username/password rules run in
the service so their messages read well in the UI.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.year_group import FIRST_YEAR, LAST_YEAR

UsernameIn = Field(min_length=1, max_length=40)
PasswordIn = Field(min_length=1, max_length=256)
YearGroupIn = Field(ge=FIRST_YEAR, le=LAST_YEAR)


class SignupRequest(BaseModel):
    username: str = UsernameIn
    password: str = PasswordIn
    year_group: int = YearGroupIn


class LoginRequest(BaseModel):
    username: str = UsernameIn
    password: str = PasswordIn


class RecoverRequest(BaseModel):
    username: str = UsernameIn
    recovery_code: str = Field(min_length=1, max_length=40)
    new_password: str = PasswordIn


class YearGroupRequest(BaseModel):
    year_group: int = YearGroupIn


class ChangePasswordRequest(BaseModel):
    current_password: str = PasswordIn
    new_password: str = PasswordIn


class PasswordConfirmRequest(BaseModel):
    password: str = PasswordIn


class MeResponse(BaseModel):
    username: str
    year_group: int | None = Field(description="Current year group; null once graduated")
    graduated: bool
    can_change_year_group: bool
    is_admin: bool
    total_xp: int
    league_tier: int
    streak_current: int
    created_at: datetime


class AuthResponse(BaseModel):
    user: MeResponse


class AuthWithRecoveryCodeResponse(AuthResponse):
    recovery_code: str = Field(description="Shown once. Only its hash is stored.")


class RecoveryCodeResponse(BaseModel):
    recovery_code: str


class UsernameIdeasResponse(BaseModel):
    ideas: list[str]
