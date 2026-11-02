"""Shared fixtures. API/DB tests run against a real Postgres (TEST_DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.deps import get_now
from app.config import Settings, asyncpg_engine_config
from app.main import create_app
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://rb:rb@localhost:5432/revision_battle_test"
)
CSRF_HEADERS = {"X-Requested-With": "rb"}
GOOD_PASSWORD = "correct horse battery"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": TEST_DATABASE_URL,
        "anthropic_api_key": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = database_url
    cfg.attributes["configure_logging"] = False
    return cfg


async def _execute(database_url: str, *statements: str) -> None:
    cfg = asyncpg_engine_config(database_url)
    engine = create_async_engine(cfg.url, connect_args=cfg.connect_args)
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    await engine.dispose()


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[str]:
    """Fresh schema for the whole run: wipe it, then `alembic upgrade head`."""
    asyncio.run(
        _execute(TEST_DATABASE_URL, "DROP SCHEMA IF EXISTS public CASCADE", "CREATE SCHEMA public")
    )
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    yield TEST_DATABASE_URL


async def truncate_all(database_url: str) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    await _execute(database_url, f"TRUNCATE {tables} RESTART IDENTITY CASCADE")


@dataclass
class Clock:
    """A controllable 'now' for the API (overrides the get_now dependency)."""

    now: datetime

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)

    def set(self, iso: str) -> None:
        self.now = datetime.fromisoformat(iso).astimezone(UTC)


@pytest.fixture
def clock() -> Clock:
    return Clock(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))


@pytest.fixture
def settings(migrated_db: str) -> Settings:
    return make_settings()


@pytest.fixture
async def app(settings: Settings, clock: Clock) -> AsyncIterator[FastAPI]:
    await truncate_all(settings.database_url)  # API tests commit for real; start clean
    application = create_app(settings)
    application.dependency_overrides[get_now] = lambda: clock.now
    async with application.router.lifespan_context(application):
        yield application


@asynccontextmanager
async def open_client(app: FastAPI, **headers: str) -> AsyncIterator[AsyncClient]:
    """A separate 'browser' with its own cookie jar."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", headers={**CSRF_HEADERS, **headers}
    ) as c:
        yield c


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with open_client(app) as c:
        yield c


async def signup(
    client: AsyncClient,
    username: str = "SwiftOtter42",
    password: str = GOOD_PASSWORD,
    year_group: int = 10,
) -> Response:
    return await client.post(
        "/api/auth/signup",
        json={"username": username, "password": password, "year_group": year_group},
    )


async def login(client: AsyncClient, username: str, password: str = GOOD_PASSWORD) -> Response:
    return await client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that's always rolled back, so tests don't leak rows."""
    await truncate_all(migrated_db)  # API tests may have left committed rows behind
    cfg = asyncpg_engine_config(migrated_db)
    engine = create_async_engine(cfg.url, connect_args=cfg.connect_args)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()
