"""Databases built like production for the auth session tests.

SQLite: a file-backed database through ``create_engine_from_url`` (WAL,
NullPool, busy timeout), so every session has its own connection, as in
production. PostgreSQL: a fresh database per test on the server named by
``ZONDARR_TEST_POSTGRES_URL`` (for example
``postgresql+asyncpg://user:password@127.0.0.1:5432/postgres``); those tests
are skipped when it is unset.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from zondarr.core.database import create_engine_from_url
from zondarr.models.base import Base

POSTGRES_URL_ENV = "ZONDARR_TEST_POSTGRES_URL"

BACKENDS = ["sqlite", "postgres"]


def postgres_url() -> str:
    """The test server's URL, or skip the test when none is configured."""
    url = os.environ.get(POSTGRES_URL_ENV)
    if not url:
        pytest.skip(f"{POSTGRES_URL_ENV} is not set")
    return url


@asynccontextmanager
async def empty_database(backend: str, tmp_path: Path) -> AsyncGenerator[str]:
    """Yield the URL of a new, empty database, dropped afterwards."""
    if backend == "sqlite":
        yield f"sqlite+aiosqlite:///{tmp_path / 'zondarr-test.db'}"
        return

    server = make_url(postgres_url())
    name = f"zondarr_test_{uuid4().hex}"
    admin = create_async_engine(server, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            _ = await conn.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield server.set(database=name).render_as_string(hide_password=False)
        finally:
            async with admin.connect() as conn:
                _ = await conn.execute(
                    text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                )
    finally:
        await admin.dispose()


@asynccontextmanager
async def production_engine(
    backend: str, tmp_path: Path
) -> AsyncGenerator[AsyncEngine]:
    """Yield an engine built by ``create_engine_from_url`` on a fresh schema."""
    async with empty_database(backend, tmp_path) as url:
        engine = create_engine_from_url(url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            yield engine
        finally:
            await engine.dispose()
