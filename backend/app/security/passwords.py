"""Password + recovery-code hashing and rules."""

from __future__ import annotations

import secrets
from functools import cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from starlette.concurrency import run_in_threadpool

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# argon2id with OWASP's recommended minimum (19 MiB, t=2, p=1). argon2-cffi's default
# uses 64 MiB per hash, which would let a handful of simultaneous logins exhaust a
# 512 MB free-tier instance.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)

_DATA = Path(__file__).parent / "data"


@cache
def _common_passwords() -> frozenset[str]:
    lines = (_DATA / "common_passwords.txt").read_text().splitlines()
    return frozenset(w for w in lines if w and not w.startswith("#"))


@cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


async def hash_secret(value: str) -> str:
    return await run_in_threadpool(_hasher.hash, value)


async def verify_secret(stored_hash: str, value: str) -> bool:
    def _verify() -> bool:
        try:
            return _hasher.verify(stored_hash, value)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    return await run_in_threadpool(_verify)


async def burn_verify_time(value: str) -> None:
    """Spend the same time as a real check, so unknown usernames aren't detectable by timing."""
    await verify_secret(_dummy_hash(), value)


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def password_problem(password: str, username: str) -> str | None:
    """A friendly reason the password isn't allowed, or None if it's fine."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Keep it under {MAX_PASSWORD_LENGTH} characters."
    if password.lower() == username.lower():
        return "Your password can't be the same as your username."
    if password.lower() in _common_passwords():
        return "That password is too common. Pick something harder to guess."
    return None


# --- Recovery codes --------------------------------------------------------------------
# 16 characters from a 31-symbol alphabet with no look-alikes (no 0/O, 1/I/L): ~79 bits.
RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_RECOVERY_LEN = 16


def new_recovery_code() -> str:
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(_RECOVERY_LEN))
    return "-".join(raw[i : i + 4] for i in range(0, _RECOVERY_LEN, 4))


def normalise_recovery_code(code: str) -> str:
    """Case, spaces and dashes don't matter when typing a code back in."""
    return "".join(ch for ch in code.upper() if ch.isalnum())
