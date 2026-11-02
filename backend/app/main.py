"""FastAPI app factory. Run with: uvicorn --factory app.main:create_app"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, health, learn, me
from app.config import Settings, get_settings
from app.db import Database
from app.errors import install_error_handlers
from app.security.csrf import CsrfMiddleware
from app.security.proxy import ProxyGuardMiddleware
from app.security.rate_limit import RateLimiter

API_PREFIX = "/api"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings)
        app.state.db = db
        app.state.limiter = RateLimiter(db.sessionmaker, settings.secret_key.get_secret_value())
        try:
            yield
        finally:
            await db.dispose()

    app = FastAPI(
        title="Revision Battle API",
        version="0.4.0",
        lifespan=lifespan,
        # API docs only outside prod. The OpenAPI schema also feeds the frontend's types.
        docs_url=None if settings.is_prod else f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else f"{API_PREFIX}/openapi.json",
    )
    app.state.settings = settings
    install_error_handlers(app)

    # Middleware: the last one added runs first. Order on the way in:
    # ProxyGuard (prod only) → CSRF → CORS → routes.
    # In prod the browser talks to the Worker on the same origin, so CORS is a second
    # line of defence; in dev it lets the Vite server call the API directly if needed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )
    app.add_middleware(
        CsrfMiddleware,
        frontend_origin=settings.frontend_origin,
        allow_localhost=not settings.is_prod,
    )
    if settings.is_prod:
        assert settings.proxy_shared_secret is not None  # enforced by Settings
        app.add_middleware(
            ProxyGuardMiddleware, shared_secret=settings.proxy_shared_secret.get_secret_value()
        )

    for router in (health.router, auth.router, me.router, learn.router, admin.router):
        app.include_router(router, prefix=API_PREFIX)
    return app
