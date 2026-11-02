"""App settings, read from environment variables (or backend/.env in dev)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-only-secret-key-change-me"  # noqa: S105 - rejected in prod below


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"

    database_url: str
    # Neon direct (non-pooled) URL for migrations. Falls back to database_url.
    database_url_direct: str | None = None

    secret_key: SecretStr = SecretStr(DEV_SECRET_KEY)
    # Shared with the Cloudflare Worker; proves a request came through the proxy.
    proxy_shared_secret: SecretStr | None = None
    frontend_origin: str = "http://localhost:5173"

    anthropic_api_key: SecretStr | None = None
    anthropic_model_generate: str = "claude-opus-5-5"
    anthropic_model_verify: str = "claude-opus-5-5"
    ai_batches_per_user_per_day: int = 5
    ai_batches_global_per_day: int = 200

    report_hide_threshold: int = 3

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def migration_database_url(self) -> str:
        return self.database_url_direct or self.database_url

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> Settings:
        if self.is_prod:
            if self.secret_key.get_secret_value() in ("", DEV_SECRET_KEY):
                raise ValueError("SECRET_KEY must be set to a real secret in prod")
            if not self.proxy_shared_secret or not self.proxy_shared_secret.get_secret_value():
                raise ValueError("PROXY_SHARED_SECRET must be set in prod")
            if not self.frontend_origin.startswith("https://"):
                raise ValueError("FRONTEND_ORIGIN must be an https:// origin in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment


@dataclass(frozen=True)
class EngineConfig:
    url: str
    connect_args: dict[str, Any] = field(default_factory=dict)


# Query params from libpq-style URLs (what Neon hands you) that asyncpg rejects.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "ssl"}
_SSL_MODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}


def asyncpg_engine_config(raw_url: str) -> EngineConfig:
    """Turn a Postgres URL (e.g. straight from the Neon dashboard) into asyncpg settings.

    - Forces the ``postgresql+asyncpg://`` scheme.
    - Moves ``sslmode=...`` into asyncpg's ``ssl`` argument and drops ``channel_binding``
      (asyncpg doesn't accept either as a query param).
    - For Neon's pooled endpoint (PgBouncer in transaction mode), turns off prepared
      statement caching and gives each prepared statement a unique name, so statements
      can't collide across pooled server connections.
    """
    parts = urlsplit(raw_url)
    if parts.scheme not in ("postgres", "postgresql", "postgresql+asyncpg"):
        raise ValueError(f"Unsupported database URL scheme: {parts.scheme!r}")

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    ssl_mode = query.get("sslmode") or query.get("ssl")
    for key in _LIBPQ_ONLY_PARAMS:
        query.pop(key, None)

    connect_args: dict[str, Any] = {}
    if ssl_mode:
        if ssl_mode not in _SSL_MODES:
            raise ValueError(f"Unsupported sslmode: {ssl_mode!r}")
        connect_args["ssl"] = ssl_mode

    host = parts.hostname or ""
    if "-pooler" in host:
        query["prepared_statement_cache_size"] = "0"
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid4()}__"

    url = urlunsplit(
        ("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return EngineConfig(url=url, connect_args=connect_args)
