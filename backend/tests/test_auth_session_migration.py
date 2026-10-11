"""The auth-session migration (75f25ededea9) on a database with legacy tokens.

Live legacy refresh tokens become one session each; revoked and expired ones
are deleted; the downgrade restores the legacy columns. SQLite runs the real
migration chain up to the previous revision. On PostgreSQL (when
``ZONDARR_TEST_POSTGRES_URL`` is set) the legacy tables are created directly
and stamped, because the initial revision does not run there (its boolean
server defaults are integers).
"""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from tests.auth_db import BACKENDS, empty_database

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
PREVIOUS = "a1b2c3d4e5f6"
REVISION = "75f25ededea9"

_legacy = sa.MetaData()
_legacy_admins = sa.Table(
    "admin_accounts",
    _legacy,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("username", sa.String(32), nullable=False),
)
_legacy_tokens = sa.Table(
    "refresh_tokens",
    _legacy,
    sa.Column(
        "admin_account_id",
        sa.Uuid(),
        sa.ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("token_hash", sa.String(64), nullable=False, index=True),
    sa.Column("expires_at", sa.DateTime(), nullable=False),
    sa.Column("revoked", sa.Boolean(), nullable=False),
    sa.Column("user_agent", sa.String(512)),
    sa.Column("ip_address", sa.String(45)),
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "created_at",
        sa.DateTime(),
        server_default=sa.text("(CURRENT_TIMESTAMP)"),
        nullable=False,
    ),
    sa.Column("updated_at", sa.DateTime()),
)
_alembic_version = sa.Table(
    "alembic_version",
    _legacy,
    sa.Column("version_num", sa.String(32), primary_key=True),
)


def _alembic(url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    return config


def _rows(url: str, sql: str) -> list[tuple[object, ...]]:
    async def query() -> list[tuple[object, ...]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(sa.text(sql))
                return [tuple(row) for row in result.all()]
        finally:
            await engine.dispose()

    return asyncio.run(query())


def _seed(url: str, *, create_legacy_tables: bool) -> dict[str, UUID]:
    """Insert one admin and three legacy tokens: live, revoked and expired."""
    now = datetime.now(UTC).replace(tzinfo=None)
    admin_id = uuid4()
    ids = {"live": uuid4(), "revoked": uuid4(), "expired": uuid4()}
    tokens = [
        ("live", False, now + timedelta(days=6)),
        ("revoked", True, now + timedelta(days=6)),
        ("expired", False, now - timedelta(days=1)),
    ]

    async def seed() -> None:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                if create_legacy_tables:
                    await conn.run_sync(_legacy.create_all)
                    _ = await conn.execute(
                        _alembic_version.insert().values(version_num=PREVIOUS)
                    )
                    _ = await conn.execute(
                        _legacy_admins.insert().values(id=admin_id, username="admin")
                    )
                else:
                    _ = await conn.execute(
                        sa.text(
                            """
                            INSERT INTO admin_accounts (id, username, auth_method,
                                enabled, totp_enabled, totp_failed_attempts, created_at)
                            VALUES (:id, 'admin', 'local', 1, 0, 0, :now)
                            """
                        ),
                        {"id": admin_id.hex, "now": now},
                    )
                for name, revoked, expires_at in tokens:
                    _ = await conn.execute(
                        _legacy_tokens.insert().values(
                            id=ids[name],
                            admin_account_id=admin_id,
                            token_hash=name,
                            expires_at=expires_at,
                            revoked=revoked,
                            user_agent=f"agent-{name}",
                            ip_address="192.0.2.1",
                            created_at=now - timedelta(days=1),
                        )
                    )
        finally:
            await engine.dispose()

    asyncio.run(seed())
    return ids


def _datetime(value: object) -> datetime:
    # Text queries return SQLite datetimes as strings.
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


@pytest.mark.parametrize("backend", BACKENDS)
def test_upgrade_moves_live_tokens_into_sessions_and_downgrade_restores_them(
    backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        async with empty_database(backend, tmp_path) as url:
            await asyncio.to_thread(_migrate, backend, url, monkeypatch)

    asyncio.run(run())


def _migrate(backend: str, url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _alembic(url, monkeypatch)
    if backend == "sqlite":
        command.upgrade(config, PREVIOUS)
        ids = _seed(url, create_legacy_tables=False)
    else:
        ids = _seed(url, create_legacy_tables=True)

    command.upgrade(config, REVISION)

    tokens = _rows(
        url, "SELECT id, session_id, generation, consumed_at FROM refresh_tokens"
    )
    assert [(_uuid(t[0]), _uuid(t[1]), t[2], t[3]) for t in tokens] == [
        (ids["live"], ids["live"], 0, None)
    ]
    sessions = _rows(
        url,
        """
        SELECT id, created_at, absolute_expires_at, current_generation, revoked_at,
            user_agent, ip_address
        FROM auth_sessions
        """,
    )
    assert len(sessions) == 1
    session_id, created_at, absolute, generation, revoked_at, agent, ip = sessions[0]
    assert _uuid(session_id) == ids["live"]
    assert _datetime(absolute) - _datetime(created_at) == timedelta(days=14)
    assert (generation, revoked_at, agent, ip) == (0, None, "agent-live", "192.0.2.1")

    command.downgrade(config, PREVIOUS)

    legacy = _rows(
        url, "SELECT id, revoked, user_agent, ip_address FROM refresh_tokens"
    )
    assert [(_uuid(t[0]), bool(t[1]), t[2], t[3]) for t in legacy] == [
        (ids["live"], False, "agent-live", "192.0.2.1")
    ]
    tables = (
        _rows(url, "SELECT name FROM sqlite_master WHERE type = 'table'")
        if backend == "sqlite"
        else _rows(url, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    assert ("auth_sessions",) not in tables

    command.upgrade(config, REVISION)
    assert len(_rows(url, "SELECT id FROM auth_sessions")) == 1


def test_sqlite_migrated_schema_matches_the_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The migrated tables have the models' columns, nullability and indexes."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'schema.db'}"
    command.upgrade(_alembic(url, monkeypatch), "head")

    with sqlite3.connect(tmp_path / "schema.db") as conn:
        inspector = sa.inspect(sa.create_engine("sqlite://", creator=lambda: conn))
        tokens = {
            c["name"]: c["nullable"] for c in inspector.get_columns("refresh_tokens")
        }
        indexes = {
            i["name"]: bool(i["unique"])
            for i in inspector.get_indexes("refresh_tokens")
        }
        foreign_keys = [
            (fk["referred_table"], fk["constrained_columns"])
            for fk in inspector.get_foreign_keys("refresh_tokens")
        ]
    assert tokens == {
        "admin_account_id": False,
        "token_hash": False,
        "expires_at": False,
        "id": False,
        "created_at": False,
        "updated_at": True,
        "session_id": False,
        "generation": False,
        "consumed_at": True,
        "revoked_at": True,
    }
    assert indexes == {
        "ix_refresh_tokens_token_hash": True,
        "ix_refresh_tokens_session_id": False,
    }
    assert ("auth_sessions", ["session_id"]) in foreign_keys
