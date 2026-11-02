"""Shared fixtures. API/DB tests run against a real Postgres (TEST_DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings, asyncpg_engine_config
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://rb:rb@localhost:5432/revision_battle_test"
)


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


def reset_schema(database_url: str) -> None:
    async def _reset() -> None:
        cfg = asyncpg_engine_config(database_url)
        engine = create_async_engine(cfg.url, connect_args=cfg.connect_args)
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(_reset())


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[str]:
    """Fresh schema for the whole run: wipe it, then `alembic upgrade head`."""
    reset_schema(TEST_DATABASE_URL)
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    yield TEST_DATABASE_URL


@pytest.fixture
def settings(migrated_db: str) -> Settings:
    return make_settings()


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c


@pytest.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that's always rolled back, so tests don't leak rows."""
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
