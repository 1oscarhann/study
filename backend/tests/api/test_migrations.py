"""The migrations must produce exactly the schema the models describe."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import asyncpg_engine_config
from app.models import Base


async def test_models_and_migrations_are_in_sync(migrated_db):
    cfg = asyncpg_engine_config(migrated_db)
    engine = create_async_engine(cfg.url, connect_args=cfg.connect_args)
    try:
        async with engine.connect() as conn:
            diff = await conn.run_sync(
                lambda sync_conn: compare_metadata(
                    MigrationContext.configure(sync_conn), Base.metadata
                )
            )
    finally:
        await engine.dispose()
    assert diff == [], f"Models changed without a migration: {diff}"
