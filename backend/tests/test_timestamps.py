"""The timestamp contract (models/base.py) and first-admin creation, on both backends.

Timestamps are stored as naive UTC and read back as aware UTC; the database's
own ``created_at`` default is UTC whatever the session time zone; and only one
first admin can be created, even by concurrent transactions. PostgreSQL runs
when ``ZONDARR_TEST_POSTGRES_URL`` is set.
"""

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from tests.auth_db import BACKENDS, production_engine
from zondarr.models.admin import AdminAccount
from zondarr.models.app_setting import AppSetting
from zondarr.models.base import Base, UTCDateTime
from zondarr.repositories.admin import AdminAccountRepository

PLUS_TWO = timezone(timedelta(hours=2))


def test_every_datetime_column_is_utc() -> None:
    """A model column outside UTCDateTime would bypass the contract."""
    others = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.sorted_tables
        for column in table.columns
        # UTCDateTime is a TypeDecorator, so it is not itself a DateTime.
        if isinstance(column.type, sa.DateTime | sa.TIMESTAMP)
    ]
    assert others == []
    utc = Base.metadata.tables["admin_accounts"].c
    assert isinstance(utc.created_at.type, UTCDateTime)
    assert isinstance(utc.last_login_at.type, UTCDateTime)


async def _setting_created_at(engine: AsyncEngine, key: str) -> datetime:
    async with async_sessionmaker(engine)() as session:
        setting = await session.get(AppSetting, key)
        assert setting is not None
        return setting.created_at


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.asyncio
async def test_aware_values_round_trip_as_the_same_utc_instant(
    backend: str, tmp_path: Path
) -> None:
    written = datetime(2026, 3, 29, 2, 30, 15, 123456, tzinfo=PLUS_TWO)
    async with production_engine(backend, tmp_path) as engine:
        async with async_sessionmaker(engine)() as session:
            session.add(AppSetting(key="aware", value="x", created_at=written))
            await session.commit()

        read = await _setting_created_at(engine, "aware")

    assert read == written
    assert read.tzinfo is UTC
    assert read.hour == 0  # 02:30+02:00 is 00:30 UTC


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.asyncio
async def test_naive_stored_values_read_back_as_utc(
    backend: str, tmp_path: Path
) -> None:
    """Rows written before the contract hold naive UTC; they read back as UTC."""
    async with production_engine(backend, tmp_path) as engine:
        async with engine.begin() as conn:
            _ = await conn.execute(
                sa.text(
                    "INSERT INTO app_settings (key, value, created_at) VALUES ('naive', 'x', :at)"
                ).bindparams(sa.bindparam("at", type_=sa.DateTime())),
                {"at": datetime(2026, 1, 1, 12, 0)},
            )

        read = await _setting_created_at(engine, "naive")

    assert read == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.asyncio
async def test_the_database_created_at_default_is_utc(
    backend: str, tmp_path: Path
) -> None:
    """An INSERT that omits created_at gets UTC, not the session's local time."""
    async with production_engine(backend, tmp_path) as engine:
        async with engine.begin() as conn:
            if backend == "postgres":
                _ = await conn.execute(sa.text("SET TIME ZONE 'America/New_York'"))
            _ = await conn.execute(
                sa.text("INSERT INTO app_settings (key, value) VALUES ('server', 'x')")
            )

        read = await _setting_created_at(engine, "server")

    assert abs(read - datetime.now(UTC)) < timedelta(minutes=1)


async def _create_first_admin(
    engine: AsyncEngine, username: str, *, hold: asyncio.Event | None = None
) -> AdminAccount | None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        admin = await AdminAccountRepository(session).create_first_admin(
            username=username,
            password_hash="not-a-real-hash",
            email=None,
            auth_method="local",
        )
        if hold is not None:
            _ = await hold.wait()
        await session.commit()
        return admin


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.asyncio
async def test_first_admin_has_its_uuid_and_a_second_is_refused(
    backend: str, tmp_path: Path
) -> None:
    async with production_engine(backend, tmp_path) as engine:
        first = await _create_first_admin(engine, "admin")
        second = await _create_first_admin(engine, "other")
        async with async_sessionmaker(engine)() as session:
            stored = (await session.execute(sa.select(AdminAccount))).scalars().all()

    assert first is not None
    assert second is None
    assert [(a.id, a.username) for a in stored] == [(first.id, "admin")]
    assert stored[0].created_at.tzinfo is UTC


async def _advisory_locks(engine: AsyncEngine, *, granted: bool) -> int:
    """Advisory locks held (granted) or waited for (not granted) on the server."""
    locks = sa.table("pg_locks", sa.column("locktype"), sa.column("granted"))
    query = (
        sa.select(sa.func.count())
        .select_from(locks)
        .where(locks.c.locktype == "advisory", locks.c.granted == granted)
    )
    async with engine.connect() as conn:
        return await conn.scalar(query) or 0


async def _until(engine: AsyncEngine, *, granted: bool, what: str) -> None:
    try:
        async with asyncio.timeout(10):
            while await _advisory_locks(engine, granted=granted) == 0:
                await asyncio.sleep(0.05)
    except TimeoutError:
        pytest.fail(f"timed out waiting until {what}")


@pytest.mark.asyncio
async def test_concurrent_first_admins_with_different_usernames_make_one(
    tmp_path: Path,
) -> None:
    """Under READ COMMITTED, the advisory lock keeps the second attempt out.

    The first transaction inserts and then holds its transaction open; the
    second, with another username that UNIQUE(username) would not stop, must
    be seen waiting for the lock before the first commits.
    """
    async with production_engine("postgres", tmp_path) as engine:
        release = asyncio.Event()
        first = asyncio.create_task(_create_first_admin(engine, "admin", hold=release))
        second: asyncio.Task[AdminAccount | None] | None = None
        try:
            await _until(engine, granted=True, what="the first attempt holds the lock")
            second = asyncio.create_task(_create_first_admin(engine, "other"))
            await _until(engine, granted=False, what="the second attempt waits for it")
            assert not second.done()
            release.set()
            created = await first
            refused = await second
        finally:
            release.set()
            for task in (first, second):
                if task is not None and not task.done():
                    _ = task.cancel()
        async with async_sessionmaker(engine)() as session:
            usernames = (
                (await session.execute(sa.select(AdminAccount.username)))
                .scalars()
                .all()
            )

    assert created is not None
    assert refused is None
    assert usernames == ["admin"]
