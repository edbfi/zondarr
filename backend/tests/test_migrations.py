"""The Alembic chain on an empty database, on SQLite and PostgreSQL.

``upgrade head`` must succeed and produce the models' schema (``alembic check``
finds nothing to generate), and ``downgrade base`` must leave only Alembic's
own table. PostgreSQL runs when ``ZONDARR_TEST_POSTGRES_URL`` is set.
"""

import asyncio
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from tests.auth_db import BACKENDS, empty_database

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _alembic(url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    return config


def _tables(url: str) -> set[str]:
    async def query() -> set[str]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                return set(
                    await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names())
                )
        finally:
            await engine.dispose()

    return asyncio.run(query())


def _chain(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _alembic(url, monkeypatch)
    command.upgrade(config, "head")
    command.check(config)  # raises if the models and the migrated schema differ

    command.downgrade(config, "base")
    assert _tables(url) == {"alembic_version"}

    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.parametrize("backend", BACKENDS)
def test_migrations_build_the_models_schema_and_downgrade_to_nothing(
    backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        async with empty_database(backend, tmp_path) as url:
            await asyncio.to_thread(_chain, url, monkeypatch)

    asyncio.run(run())
