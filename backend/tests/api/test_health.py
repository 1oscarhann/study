async def test_health_reports_db_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


async def test_openapi_is_served_outside_prod(client):
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Revision Battle API"
