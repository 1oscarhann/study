"""Account settings: year group, password, recovery code, deletion."""

from tests.conftest import GOOD_PASSWORD, login, open_client, signup

# --- year group --------------------------------------------------------------------------


async def test_year_group_rolls_over_at_midnight_uk_time_on_1_september(client, clock):
    clock.set("2027-08-31T22:59:00+00:00")  # 23:59 BST, 31 Aug
    await signup(client, year_group=11)
    assert (await client.get("/api/me")).json()["year_group"] == 11
    clock.set("2027-08-31T23:00:00+00:00")  # 00:00 BST, 1 Sept
    assert (await client.get("/api/me")).json()["year_group"] == 12


async def test_year_13s_graduate_on_1_september(client, clock):
    clock.set("2027-06-01T12:00:00+00:00")
    await signup(client, year_group=13)
    clock.set("2027-09-01T09:00:00+00:00")
    await login(client, "SwiftOtter42")  # 3 months later the old session has expired
    me = (await client.get("/api/me")).json()
    assert me["graduated"] is True
    assert me["year_group"] is None


async def test_year_group_can_be_corrected_once_per_school_year(client, clock):
    await signup(client, year_group=10)

    # Picking the same year again is a no-op and doesn't use up the correction.
    same = await client.patch("/api/me/year-group", json={"year_group": 10})
    assert same.status_code == 200 and same.json()["can_change_year_group"] is True

    first = await client.patch("/api/me/year-group", json={"year_group": 11})
    assert first.status_code == 200
    assert first.json()["year_group"] == 11
    assert first.json()["can_change_year_group"] is False

    second = await client.patch("/api/me/year-group", json={"year_group": 9})
    assert second.status_code == 409
    assert "1 September" in second.json()["detail"]

    clock.set("2027-08-31T12:00:00+00:00")  # still the same school year
    await login(client, "SwiftOtter42")
    assert (await client.patch("/api/me/year-group", json={"year_group": 9})).status_code == 409

    clock.set("2027-09-01T12:00:00+00:00")  # new school year: you're now Year 12, can fix again
    await login(client, "SwiftOtter42")
    me = (await client.get("/api/me")).json()
    assert me["year_group"] == 12 and me["can_change_year_group"] is True
    assert (await client.patch("/api/me/year-group", json={"year_group": 11})).status_code == 200


async def test_year_group_must_be_7_to_13(client):
    await signup(client)
    for bad in (6, 14):
        resp = await client.patch("/api/me/year-group", json={"year_group": bad})
        assert resp.status_code == 422
        assert resp.json()["field"] == "year_group"


async def test_settings_need_you_to_be_logged_in(client):
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.patch("/api/me/year-group", json={"year_group": 9})).status_code == 401
    resp = await client.request("DELETE", "/api/me", json={"password": "x"})
    assert resp.status_code == 401


# --- password ----------------------------------------------------------------------------


async def test_change_password_logs_out_other_devices_only(app):
    async with open_client(app) as phone, open_client(app) as laptop:
        await signup(phone)
        await login(laptop, "SwiftOtter42")

        wrong = await phone.post(
            "/api/me/password",
            json={"current_password": "nope nope", "new_password": "brand new passphrase"},
        )
        assert wrong.status_code == 401
        assert wrong.json()["field"] == "current_password"

        weak = await phone.post(
            "/api/me/password",
            json={"current_password": GOOD_PASSWORD, "new_password": "password"},
        )
        assert weak.status_code == 422
        assert weak.json()["field"] == "new_password"

        ok = await phone.post(
            "/api/me/password",
            json={"current_password": GOOD_PASSWORD, "new_password": "brand new passphrase"},
        )
        assert ok.status_code == 204
        assert (await phone.get("/api/me")).status_code == 200
        assert (await laptop.get("/api/me")).status_code == 401


async def test_password_checks_are_rate_limited(client):
    await signup(client)
    body = {"current_password": "nope nope", "new_password": "brand new passphrase"}
    for _ in range(10):
        assert (await client.post("/api/me/password", json=body)).status_code == 401
    assert (await client.post("/api/me/password", json=body)).status_code == 429


# --- recovery code -----------------------------------------------------------------------


async def test_new_recovery_code_replaces_the_old_one(client):
    old = (await signup(client)).json()["recovery_code"]
    assert (
        await client.post("/api/me/recovery-code", json={"password": "wrong pass"})
    ).status_code == 401

    resp = await client.post("/api/me/recovery-code", json={"password": GOOD_PASSWORD})
    new = resp.json()["recovery_code"]
    assert resp.status_code == 200 and new != old

    async def try_code(code):
        return await client.post(
            "/api/auth/recover",
            json={
                "username": "SwiftOtter42",
                "recovery_code": code,
                "new_password": "brand new passphrase",
            },
        )

    assert (await try_code(old)).status_code == 401
    assert (await try_code(new)).status_code == 200


# --- deletion ----------------------------------------------------------------------------


async def test_delete_account_removes_everything(app, client):
    await signup(client)
    wrong = await client.request("DELETE", "/api/me", json={"password": "nope nope"})
    assert wrong.status_code == 401

    resp = await client.request("DELETE", "/api/me", json={"password": GOOD_PASSWORD})
    assert resp.status_code == 204
    assert (await client.get("/api/me")).status_code == 401

    from sqlalchemy import func, select

    from app.models import AuthSession, User

    async with app.state.db.sessionmaker() as s:
        assert await s.scalar(select(func.count()).select_from(User)) == 0
        assert await s.scalar(select(func.count()).select_from(AuthSession)) == 0

    # The username is free again.
    async with open_client(app) as c:
        assert (await signup(c)).status_code == 201
