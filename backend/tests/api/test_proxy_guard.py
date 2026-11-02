"""In prod the API only answers requests that came through the Cloudflare Worker."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.conftest import make_settings

SECRET = "shared-with-the-worker"


@pytest.fixture
async def prod_client(migrated_db) -> AsyncIterator[AsyncClient]:
    settings = make_settings(
        environment="prod",
        secret_key="a-real-secret-that-is-long-enough",
        proxy_shared_secret=SECRET,
        frontend_origin="https://revision-battle.example.workers.dev",
    )
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
