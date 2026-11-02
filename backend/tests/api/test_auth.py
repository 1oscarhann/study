"""Signup, login, logout, sessions, recovery, CSRF, rate limits."""

import re
from datetime import timedelta

import pytest

from app.security import rate_limit as rl
from tests.conftest import GOOD_PASSWORD, login, open_client, signup

CODE_RE = re.compile(r"^[A-Z2-9]{4}(-[A-Z2-9]{4}){3}$")


# --- signup ------------------------------------------------------------------------------


async def test_signup_logs_you_in_and_returns_a_recovery_code_once(client):
    resp = await signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert CODE_RE.match(body["recovery_code"])
    assert body["user"] == {
        "username": "SwiftOtter42",
        "year_group": 10,
        "graduated": False,
        "can_change_year_group": True,
        "is_admin": False,
        "total_xp": 0,
        "league_tier": 0,
        "streak_current": 0,
        "created_at": body["user"]["created_at"],
    }
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith("rb_session=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie

    me = await client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["username"] == "SwiftOtter42"
    assert "recovery_code" not in me.json()


async def test_signup_stores_nothing_but_the_basics(client, app):
    await signup(client)
    from sqlalchemy import select

    from app.models import User

    async with app.state.db.sessionmaker() as s:
        user = (await s.scalars(select(User))).one()
    assert user.password_hash.startswith("$argon2id$")
    assert GOOD_PASSWORD not in user.password_hash
    assert user.cohort_year == 2023  # Year 10 in Nov 2026


async def test_usernames_are_unique_ignoring_case(client):
    assert (await signup(client, "SwiftOtter42")).status_code == 201
    async with open_client(client._transport.app) as other:  # type: ignore[attr-defined]
        resp = await signup(other, "swiftOTTER42")
    assert resp.status_code == 409
    assert resp.json()["field"] == "username"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"username": "ab"}, "username"),
        ({"username": "xXsh1tXx"}, "username"),
        ({"username": "admin"}, "username"),
        ({"password": "short"}, "password"),
        ({"password": "football"}, "password"),
        ({"year_group": 6}, "year_group"),
        ({"year_group": 14}, "year_group"),
        ({"year_group": "Year 10"}, "year_group"),
    ],
)
async def test_signup_explains_what_is_wrong(client, payload, field):
    data = {"username": "SwiftOtter42", "password": GOOD_PASSWORD, "year_group": 10, **payload}
    resp = await client.post("/api/auth/signup", json=data)
    assert resp.status_code == 422
    assert resp.json()["field"] == field
    assert resp.json()["detail"]


async def test_signup_rejects_extra_personal_fields_silently_ignored(client):
    # Extra fields (e.g. an email) are never stored; the model simply doesn't have them.
    resp = await client.post(
        "/api/auth/signup",
        json={
            "username": "SwiftOtter42",
            "password": GOOD_PASSWORD,
            "year_group": 10,
            "email": "kid@example.com",
            "real_name": "Sam",
        },
    )
    assert resp.status_code == 201
    assert "email" not in resp.text and "Sam" not in resp.text


async def test_username_ideas_are_valid_and_free(client):
    await signup(client, "SwiftOtter42")
    resp = await client.get("/api/auth/username-ideas")
    ideas = resp.json()["ideas"]
    assert len(ideas) == 5
    assert all(re.fullmatch(r"[A-Za-z0-9_]{3,20}", i) for i in ideas)


# --- login / logout / sessions ---------------------------------------------------------------


async def test_login_and_logout(app):
    async with open_client(app) as a:
        await signup(a)
    async with open_client(app) as b:
        assert (await b.get("/api/me")).status_code == 401
        resp = await login(b, "swiftotter42")  # username is case-insensitive
        assert resp.status_code == 200
        assert resp.json()["user"]["username"] == "SwiftOtter42"
        assert (await b.get("/api/me")).status_code == 200

        old_cookie = b.cookies.get("rb_session")
        out = await b.post("/api/auth/logout")
        assert out.status_code == 204
        assert (await b.get("/api/me")).status_code == 401

        # Replaying the old token doesn't work either: the session is gone server-side.
        b.cookies.set("rb_session", old_cookie)
        assert (await b.get("/api/me")).status_code == 401


async def test_wrong_password_and_unknown_user_look_the_same(client):
    await signup(client)
    wrong = await login(client, "SwiftOtter42", "not the password")
    unknown = await login(client, "NobodyHere", "whatever123")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Wrong username or password."


async def test_ten_failed_logins_lock_that_username_for_a_while(client, clock):
    await signup(client)
    for _ in range(10):
        assert (await login(client, "SwiftOtter42", "nope nope nope")).status_code == 401
    locked = await login(client, "SwiftOtter42")  # even the right password
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0
    assert "Try again in" in locked.json()["detail"]

    clock.advance(minutes=16)
    assert (await login(client, "SwiftOtter42")).status_code == 200


async def test_failed_logins_on_one_username_dont_lock_others(client):
    await signup(client, "SwiftOtter42")
    async with open_client(client._transport.app) as other:  # type: ignore[attr-defined]
        await signup(other, "CosmicPanda11")
    for _ in range(10):
        await login(client, "SwiftOtter42", "nope nope nope")
    assert (await login(client, "CosmicPanda11")).status_code == 200


async def test_signup_is_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(rl, "SIGNUP_PER_IP", rl.Limit("signup-ip", 3, timedelta(hours=1)))
    for i in range(3):
        assert (await signup(client, f"Student_{i}aa")).status_code == 201
    assert (await signup(client, "Student_4aa")).status_code == 429


async def test_sessions_expire_after_30_days_without_use(client, clock):
    await signup(client)
    clock.advance(days=31)
    assert (await client.get("/api/me")).status_code == 401


async def test_using_the_app_keeps_you_logged_in(client, clock):
    await signup(client)
    for _ in range(4):  # visit every 20 days for 80 days
        clock.advance(days=20)
        assert (await client.get("/api/me")).status_code == 200


# --- CSRF --------------------------------------------------------------------------------


async def test_state_changes_need_the_csrf_header(app):
    async with open_client(app) as c:
        resp = await c.post(
            "/api/auth/signup",
            json={"username": "SwiftOtter42", "password": GOOD_PASSWORD, "year_group": 10},
            headers={"X-Requested-With": ""},
        )
    assert resp.status_code == 403
    assert resp.json()["code"] == "csrf"


async def test_foreign_origins_are_blocked(app):
    async with open_client(app, Origin="https://evil.example") as c:
        resp = await signup(c)
    assert resp.status_code == 403


async def test_frontend_and_localhost_origins_are_fine_in_dev(app):
    async with open_client(app, Origin="http://localhost:5173") as c:
        assert (await signup(c, "SwiftOtter42")).status_code == 201
    async with open_client(app, Origin="http://127.0.0.1:8787") as c:
        assert (await signup(c, "CosmicPanda11")).status_code == 201


async def test_reads_dont_need_the_csrf_header(app):
    async with open_client(app, **{"X-Requested-With": ""}) as c:
        assert (await c.get("/api/health")).status_code == 200


# --- recovery ----------------------------------------------------------------------------


async def test_recovery_code_resets_the_password_and_logs_out_everywhere(app):
    async with open_client(app) as phone:
        code = (await signup(phone)).json()["recovery_code"]
        async with open_client(app) as laptop:
            resp = await laptop.post(
                "/api/auth/recover",
                json={
                    "username": "swiftotter42",
                    "recovery_code": code.lower().replace("-", " "),  # typos in case/spacing ok
                    "new_password": "brand new passphrase",
                },
            )
            assert resp.status_code == 200
            new_code = resp.json()["recovery_code"]
            assert CODE_RE.match(new_code) and new_code != code
            assert (await laptop.get("/api/me")).status_code == 200
        assert (await phone.get("/api/me")).status_code == 401  # old session revoked

    async with open_client(app) as c:
        assert (await login(c, "SwiftOtter42", GOOD_PASSWORD)).status_code == 401
        assert (await login(c, "SwiftOtter42", "brand new passphrase")).status_code == 200
        # The old code is used up.
        reuse = await c.post(
            "/api/auth/recover",
            json={"username": "SwiftOtter42", "recovery_code": code, "new_password": "x" * 12},
        )
        assert reuse.status_code == 401


async def test_wrong_recovery_code(client):
    await signup(client)
    resp = await client.post(
        "/api/auth/recover",
        json={
            "username": "SwiftOtter42",
            "recovery_code": "AAAA-BBBB-CCCC-DDDD",
            "new_password": "brand new passphrase",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "bad_recovery_code"


async def test_recovery_attempts_are_limited_per_username(client):
    await signup(client)
    body = {
        "username": "SwiftOtter42",
        "recovery_code": "AAAA-BBBB-CCCC-DDDD",
        "new_password": "brand new passphrase",
    }
    for _ in range(5):
        assert (await client.post("/api/auth/recover", json=body)).status_code == 401
    assert (await client.post("/api/auth/recover", json=body)).status_code == 429


async def test_weak_new_password_doesnt_burn_a_recovery_attempt(client):
    code = (await signup(client)).json()["recovery_code"]
    weak = {"username": "SwiftOtter42", "recovery_code": code, "new_password": "password"}
    for _ in range(6):
        resp = await client.post("/api/auth/recover", json=weak)
        assert resp.status_code == 422
        assert resp.json()["field"] == "new_password"
    good = {**weak, "new_password": "brand new passphrase"}
    assert (await client.post("/api/auth/recover", json=good)).status_code == 200
