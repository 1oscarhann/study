import pytest
from pydantic import ValidationError

from app.config import DEV_SECRET_KEY, Settings, asyncpg_engine_config

NEON_POOLED = (
    "postgresql://app:pw@ep-cool-name-123456-pooler.eu-west-2.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_DIRECT = (
    "postgresql://app:pw@ep-cool-name-123456.eu-west-2.aws.neon.tech/neondb?sslmode=require"
)


def test_neon_pooled_url_is_made_asyncpg_and_pgbouncer_safe():
    cfg = asyncpg_engine_config(NEON_POOLED)
    assert cfg.url.startswith("postgresql+asyncpg://app:pw@ep-cool-name-123456-pooler.")
    assert "sslmode" not in cfg.url
    assert "channel_binding" not in cfg.url
    assert "prepared_statement_cache_size=0" in cfg.url
    assert cfg.connect_args["ssl"] == "require"
    assert cfg.connect_args["statement_cache_size"] == 0
    name_func = cfg.connect_args["prepared_statement_name_func"]
    assert name_func() != name_func()  # unique names avoid collisions behind PgBouncer


def test_neon_direct_url_keeps_statement_cache():
    cfg = asyncpg_engine_config(NEON_DIRECT)
    assert cfg.connect_args == {"ssl": "require"}
    assert "prepared_statement_cache_size" not in cfg.url


def test_local_url_has_no_ssl():
    cfg = asyncpg_engine_config("postgresql://rb:rb@localhost:5432/revision_battle")
    assert cfg.url == "postgresql+asyncpg://rb:rb@localhost:5432/revision_battle"
    assert cfg.connect_args == {}


@pytest.mark.parametrize("url", ["mysql://x@y/z", "sqlite:///x.db"])
def test_rejects_non_postgres_urls(url):
    with pytest.raises(ValueError, match="scheme"):
        asyncpg_engine_config(url)


def test_rejects_unknown_sslmode():
    with pytest.raises(ValueError, match="sslmode"):
        asyncpg_engine_config("postgresql://a@b/c?sslmode=yolo")


def _prod(**overrides):
    values = {
        "environment": "prod",
        "database_url": NEON_POOLED,
        "secret_key": "a-real-secret-that-is-long-enough",
        "proxy_shared_secret": "shared-with-the-worker",
        "frontend_origin": "https://revision-battle.example.workers.dev",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_prod_settings_accept_real_secrets():
    assert _prod().is_prod


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"secret_key": DEV_SECRET_KEY}, "SECRET_KEY"),
        ({"proxy_shared_secret": None}, "PROXY_SHARED_SECRET"),
        ({"proxy_shared_secret": ""}, "PROXY_SHARED_SECRET"),
        ({"frontend_origin": "http://insecure.example"}, "FRONTEND_ORIGIN"),
    ],
)
def test_prod_settings_reject_unsafe_config(override, message):
    with pytest.raises(ValidationError, match=message):
        _prod(**override)


def test_migration_url_prefers_direct():
    s = _prod(database_url_direct=NEON_DIRECT)
    assert s.migration_database_url == NEON_DIRECT
    assert _prod().migration_database_url == NEON_POOLED
