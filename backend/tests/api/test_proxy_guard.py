"""In prod the API only answers requests that came through the Cloudflare Worker."""

from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.security import rate_limit as rl
from tests.conftest import GOOD_PASSWORD, make_settings, truncate_all

SECRET = "shared-with-the-worker"


@pytest.fixture
async def prod_client(migrated_db) -> AsyncIterator[AsyncClient]:
    settings = make_settings(
        environment="prod",
        secret_key="a-real-secret-that-is-long-enough",
        proxy_shared_secret=SECRET,
        frontend_origin="https://revision-battle.example.workers.dev",
    )
    await truncate_all(settings.database_url)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c


async def test_direct_requests_without_secret_are_refused(prod_client):
    resp = await prod_client.get("/api/anything")
    assert resp.status_code == 403


async def test_wrong_secret_is_refused(prod_client):
    resp = await prod_client.get("/api/anything", headers={"X-Proxy-Secret": "nope"})
    assert resp.status_code == 403


async def test_requests_via_the_worker_get_through(prod_client):
    resp = await prod_client.get("/api/anything", headers={"X-Proxy-Secret": SECRET})
    assert resp.status_code == 404  # reached the app; route just doesn't exist


async def test_health_check_is_exempt_for_render(prod_client):
    resp = await prod_client.get("/api/health")
    assert resp.status_code == 200


async def test_docs_are_hidden_in_prod(prod_client):
    resp = await prod_client.get("/api/openapi.json", headers={"X-Proxy-Secret": SECRET})
    assert resp.status_code == 404


def _via_worker(ip: str = "203.0.113.7") -> dict[str, str]:
    return {
        "X-Proxy-Secret": SECRET,
        "X-Client-IP": ip,
        "X-Requested-With": "rb",
        "Origin": "https://revision-battle.example.workers.dev",
    }


def _signup_body(username: str) -> dict[str, object]:
    return {"username": username, "password": GOOD_PASSWORD, "year_group": 10}


async def test_prod_session_cookie_is_host_only_and_secure(prod_client):
    resp = await prod_client.post(
        "/api/auth/signup", json=_signup_body("SwiftOtter42"), headers=_via_worker()
    )
    assert resp.status_code == 201
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith("__Host-rb_session=")
    for attr in ("Secure", "HttpOnly", "SameSite=lax", "Path=/"):
        assert attr in cookie
    assert "Domain" not in cookie


async def test_prod_rejects_localhost_origins(prod_client):
    headers = {**_via_worker(), "Origin": "http://localhost:5173"}
    resp = await prod_client.post(
        "/api/auth/signup", json=_signup_body("SwiftOtter42"), headers=headers
    )
    assert resp.status_code == 403


async def test_per_ip_limits_use_the_ip_the_worker_reports(prod_client, monkeypatch):
    monkeypatch.setattr(rl, "SIGNUP_PER_IP", rl.Limit("signup-ip", 1, timedelta(hours=1)))
    a1 = await prod_client.post(
        "/api/auth/signup", json=_signup_body("Student_aa1"), headers=_via_worker("198.51.100.1")
    )
    a2 = await prod_client.post(
        "/api/auth/signup", json=_signup_body("Student_aa2"), headers=_via_worker("198.51.100.1")
    )
    b1 = await prod_client.post(
        "/api/auth/signup", json=_signup_body("Student_bb1"), headers=_via_worker("198.51.100.2")
    )
    assert (a1.status_code, a2.status_code, b1.status_code) == (201, 429, 201)
