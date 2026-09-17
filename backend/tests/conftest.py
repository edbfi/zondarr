"""Shared test fixtures and Hypothesis configuration.

This module configures Hypothesis profiles for different environments
and provides shared fixtures for property-based tests.
"""

from collections.abc import AsyncGenerator

import pytest
from hypothesis import HealthCheck, Phase, Verbosity, settings
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

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


async def create_test_engine() -> AsyncEngine:
    """Create an async SQLite engine for testing.

    This function creates a fresh in-memory database for each call,
    ensuring complete isolation between Hypothesis examples.
    """
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

# Tables in deletion order (children before parents) to respect FK constraints.
_TRUNCATE_ORDER: list[str] = [
    "oauth_sessions",
    "refresh_tokens",
    "sync_runs",
    "admin_accounts",
    "wizard_step_translations",
    "step_interactions",
    "wizard_steps",
    "wizards",
    "users",
    "invitation_libraries",
    "invitation_servers",
    "invitations",
    "libraries",
    "identities",
    "media_servers",
    "app_settings",
]


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
                for table in _TRUNCATE_ORDER:
                    _ = await conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608

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
