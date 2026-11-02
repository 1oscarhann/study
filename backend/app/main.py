"""FastAPI app factory. Run with: uvicorn --factory app.main:create_app"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.config import Settings, get_settings
from app.db import Database
from app.security.proxy import ProxyGuardMiddleware

API_PREFIX = "/api"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db = Database(settings)
        try:
            yield
        finally:
            await app.state.db.dispose()

    app = FastAPI(
        title="Revision Battle API",
        version="0.1.0",
        lifespan=lifespan,
        # API docs only outside prod. The OpenAPI schema also feeds the frontend's types.
        docs_url=None if settings.is_prod else f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else f"{API_PREFIX}/openapi.json",
    )
    app.state.settings = settings

    # In prod the browser talks to the Worker on the same origin, so CORS is a second
    # line of defence; in dev it lets the Vite server call the API directly if needed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )
    if settings.is_prod:
        assert settings.proxy_shared_secret is not None  # enforced by Settings
        app.add_middleware(
            ProxyGuardMiddleware, shared_secret=settings.proxy_shared_secret.get_secret_value()
        )

    app.include_router(health.router, prefix=API_PREFIX)
    return app
