"""Shared test fixtures and Hypothesis configuration.

This module configures Hypothesis profiles for different environments
and provides shared fixtures for property-based tests.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, Phase, Verbosity, settings
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry, NullPool

import zondarr.models as _zondarr_models  # Ensure all model tables are registered
from zondarr.models.base import Base

_ = _zondarr_models

# =============================================================================
# Hypothesis Profile Configuration
# =============================================================================

# Default profile: balanced for local development
settings.register_profile(
    "default",
    max_examples=15,  # Reduced from 30 for faster feedback
    deadline=None,  # Disable deadline for async tests with I/O
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
    phases=[Phase.explicit, Phase.reuse, Phase.generate],  # No shrink for speed
    verbosity=Verbosity.normal,
)

# CI profile: same as default for continuous integration
settings.register_profile(
    "ci",
    max_examples=15,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
    phases=[Phase.explicit, Phase.reuse, Phase.generate],
    verbosity=Verbosity.quiet,
)

# Fast profile: minimal examples for quick feedback during development
settings.register_profile(
    "fast",
    max_examples=5,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
    phases=[Phase.explicit, Phase.reuse, Phase.generate],
    verbosity=Verbosity.quiet,
)

# Debug profile: for investigating failing tests with shrinking
settings.register_profile(
    "debug",
    max_examples=100,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
    verbosity=Verbosity.verbose,
)

# Load the default profile (can be overridden via HYPOTHESIS_PROFILE env var)
settings.load_profile("default")


# =============================================================================
# Shared Test Constants
# =============================================================================

KNOWN_SERVER_TYPES: list[str] = ["jellyfin", "plex"]
"""Server types registered in the provider registry, used across test strategies."""


# =============================================================================
# Database Helper Functions
# =============================================================================


POSTGRES_URL_ENV = "ZONDARR_TEST_POSTGRES_URL"
"""Server URL that switches the shared fixtures to PostgreSQL (see tests/auth_db.py)."""

# This process's PostgreSQL test database, created on first use and dropped
# when the session ends. The name is unique to this process, so parallel xdist
# workers and concurrent pytest runs on one server never share or drop each
# other's databases.
_postgres_database: list[str] = []


async def _postgres_test_url(server_url: str) -> str:
    """The URL of this process's test database, created on first use."""
    server = make_url(server_url)
    if not _postgres_database:
        name = f"zondarr_test_{uuid4().hex}"
        admin = create_async_engine(server, isolation_level="AUTOCOMMIT")
        try:
            async with admin.connect() as conn:
                _ = await conn.execute(text(f'CREATE DATABASE "{name}"'))
        finally:
            await admin.dispose()
        _postgres_database.append(name)
    return server.set(database=_postgres_database[0]).render_as_string(
        hide_password=False
    )


async def _drop_postgres_test_database(server_url: str, name: str) -> None:
    admin = create_async_engine(make_url(server_url), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            _ = await conn.execute(
                text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            )
    finally:
        await admin.dispose()


def pytest_sessionfinish() -> None:
    """Drop this process's PostgreSQL test database, if one was created."""
    server_url = os.environ.get(POSTGRES_URL_ENV)
    if server_url and _postgres_database:
        asyncio.run(_drop_postgres_test_database(server_url, _postgres_database.pop()))


async def create_test_engine() -> AsyncEngine:
    """Create an async engine on an empty database with the models' schema.

    SQLite (the default): a fresh in-memory database per call, ensuring
    complete isolation between Hypothesis examples. PostgreSQL (when
    ``ZONDARR_TEST_POSTGRES_URL`` is set): this worker's database with every
    table emptied. Its engine pools nothing, because an asyncpg connection is
    bound to the event loop that opened it, and Litestar's test clients run
    the app on a loop of their own.
    """
    server_url = os.environ.get(POSTGRES_URL_ENV)
    if server_url:
        engine = create_async_engine(
            await _postgres_test_url(server_url), poolclass=NullPool
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for table in reversed(Base.metadata.sorted_tables):
                _ = await conn.execute(table.delete())
        return engine

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(
        dbapi_connection: object,
        _connection_record: ConnectionPoolEntry,
    ) -> None:
        cursor = dbapi_connection.cursor()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]
        cursor.execute("PRAGMA foreign_keys=ON")  # pyright: ignore[reportUnknownMemberType]
        cursor.close()  # pyright: ignore[reportUnknownMemberType]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


# =============================================================================
# Reusable Test Database (for Hypothesis @given tests)
# =============================================================================


class TestDB:
    """Reusable test database — creates engine once, truncates between examples.

    Use this in @given tests to avoid recreating the engine+schema per Hypothesis
    example. Call ``await db.clean()`` at the start of each example.
    """

    __test__: bool = False  # Tell pytest this is not a test class

    _engine: AsyncEngine | None
    _session_factory: async_sessionmaker[AsyncSession] | None

    def __init__(self) -> None:
        self._engine = None
        self._session_factory = None

    async def clean(self) -> None:
        """Prepare DB for the next example.

        First call creates the engine + schema. Subsequent calls truncate all
        tables via DELETE (much faster than recreating the engine).
        """
        if self._engine is None:
            self._engine = await create_test_engine()
            self._session_factory = async_sessionmaker(
                self._engine, expire_on_commit=False
            )
        else:
            async with self._engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    _ = await conn.execute(table.delete())

    @property
    def engine(self) -> AsyncEngine:
        """Return the engine (must call ``clean()`` first)."""
        assert self._engine is not None, "call clean() before accessing engine"
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the session factory (must call ``clean()`` first)."""
        assert self._session_factory is not None, (
            "call clean() before accessing session_factory"
        )
        return self._session_factory

    async def dispose(self) -> None:
        """Dispose the engine (called by the fixture teardown)."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


@pytest.fixture
async def db() -> AsyncGenerator[TestDB]:
    """Provide a reusable TestDB instance for @given tests."""
    test_db = TestDB()
    yield test_db
    await test_db.dispose()


# =============================================================================
# Shared Database Fixtures
# =============================================================================


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """Create a shared async SQLite engine for testing.

    This fixture creates a single engine per test function.
    For tests that need isolation between Hypothesis examples,
    use create_test_engine() directly in the test.
    """
    engine = await create_test_engine()
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the test engine."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Create a database session for testing."""
    async with session_factory() as session:
        yield session
