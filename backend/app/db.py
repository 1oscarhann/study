"""Async database engine and the per-request session dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, asyncpg_engine_config


class Database:
    def __init__(self, settings: Settings) -> None:
        cfg = asyncpg_engine_config(settings.database_url)
        self.engine: AsyncEngine = create_async_engine(
            cfg.url,
            connect_args=cfg.connect_args,
            # Neon suspends idle computes and drops connections; check before use.
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=5,
        )
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_session)]
