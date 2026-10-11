"""Auth sessions: refresh rotation, lost-answer recovery, replay and logout.

Every test runs against databases built like production (see
``tests/auth_db.py``): a file-backed SQLite database, and PostgreSQL when
``ZONDARR_TEST_POSTGRES_URL`` is set. Each service call runs in its own
session and transaction, committed on success and rolled back on an
exception, as ``provide_db_session`` does for a request.
"""

import asyncio
import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from litestar.datastructures import State
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.auth_db import BACKENDS, production_engine
from zondarr.config import Settings
from zondarr.core.exceptions import AuthenticationError
from zondarr.core.tasks import BackgroundTaskManager
from zondarr.models.admin import AdminAccount, AuthSession, RefreshToken
from zondarr.repositories.admin import (
    AdminAccountRepository,
    AuthSessionRepository,
    RefreshTokenRepository,
)
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import (
    MAX_LIVE_TOKENS_PER_SESSION,
    REFRESH_TOKEN_EXPIRY_DAYS,
    SESSION_ABSOLUTE_DAYS,
    AuthService,
    Rotation,
)

type Factory = async_sessionmaker[AsyncSession]

CLEANUP_SECRET_KEY = "test-secret-key-for-session-cleanup-at-least-32"  # noqa: S105


@pytest.fixture(params=BACKENDS)
async def factory(
    request: pytest.FixtureRequest, tmp_path: Path
) -> AsyncGenerator[Factory]:
    backend: str = request.param  # pyright: ignore[reportAny]
    async with production_engine(backend, tmp_path) as engine:
        yield async_sessionmaker(engine, expire_on_commit=False)


# =============================================================================
# Helpers
# =============================================================================


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _service(session: AsyncSession) -> AuthService:
    return AuthService(
        admin_repo=AdminAccountRepository(session),
        session_repo=AuthSessionRepository(session),
        token_repo=RefreshTokenRepository(session),
        app_setting_repo=AppSettingRepository(session),
    )


async def _create_admin(
    factory: Factory, *, username: str = "admin", enabled: bool = True
) -> UUID:
    async with factory() as session:
        admin = AdminAccount(
            username=username,
            password_hash="not-a-real-hash",
            auth_method="local",
            enabled=enabled,
        )
        session.add(admin)
        await session.commit()
        return admin.id


async def _start(factory: Factory, admin_id: UUID) -> tuple[UUID, str]:
    async with factory() as session:
        admin = await AdminAccountRepository(session).get_by_id(admin_id)
        assert admin is not None
        started = await _service(session).start_session(
            admin, user_agent="pytest", ip="127.0.0.1"
        )
        await session.commit()
        return started


async def _rotate(factory: Factory, raw: str) -> Rotation:
    async with factory() as session:
        try:
            rotation = await _service(session).rotate(raw)
            await session.commit()
            return rotation
        except Exception:
            await session.rollback()
            raise


async def _rotate_error(factory: Factory, raw: str) -> str:
    with pytest.raises(AuthenticationError) as exc_info:
        _ = await _rotate(factory, raw)
    return exc_info.value.error_code


async def _end(
    factory: Factory, *, raw: str | None = None, session_id: UUID | None = None
) -> bool:
    async with factory() as session:
        ended = await _service(session).end_session(
            raw_refresh=raw, session_id=session_id, reason="logout"
        )
        await session.commit()
        return ended


async def _session(factory: Factory, session_id: UUID) -> AuthSession:
    async with factory() as session:
        found = await session.get(AuthSession, session_id)
        assert found is not None
        return found


async def _token(factory: Factory, raw: str) -> RefreshToken:
    async with factory() as session:
        found = await RefreshTokenRepository(session).get_by_token_hash(_hash(raw))
        assert found is not None
        return found


async def _tokens(factory: Factory, session_id: UUID) -> list[RefreshToken]:
    async with factory() as session:
        result = await session.scalars(
            select(RefreshToken)
            .where(RefreshToken.session_id == session_id)
            .order_by(RefreshToken.created_at)
        )
        return list(result.unique().all())


def _live(tokens: list[RefreshToken]) -> list[RefreshToken]:
    return [t for t in tokens if t.consumed_at is None and t.revoked_at is None]


async def _set_token_expiry(factory: Factory, raw: str, expires_at: datetime) -> None:
    async with factory() as session:
        _ = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == _hash(raw))
            .values(expires_at=expires_at)
        )
        await session.commit()


async def _set_absolute_expiry(
    factory: Factory, session_id: UUID, absolute_expires_at: datetime
) -> None:
    async with factory() as session:
        _ = await session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id)
            .values(absolute_expires_at=absolute_expires_at)
        )
        await session.commit()


def _close(a: datetime, b: datetime) -> bool:
    return abs(a - b) < timedelta(minutes=1)


# =============================================================================
# start_session / rotate
# =============================================================================


class TestRotate:
    async def test_start_session_issues_generation_zero(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        session_id, raw = await _start(factory, admin_id)

        auth_session = await _session(factory, session_id)
        token = await _token(factory, raw)
        now = datetime.now(UTC)
        assert auth_session.admin_account_id == admin_id
        assert auth_session.current_generation == 0
        assert auth_session.revoked_at is None
        assert auth_session.user_agent == "pytest"
        assert _close(
            auth_session.absolute_expires_at,
            now + timedelta(days=SESSION_ABSOLUTE_DAYS),
        )
        assert token.session_id == session_id
        assert token.generation == 0
        assert token.consumed_at is None
        assert _close(token.expires_at, now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS))

    async def test_rotate_consumes_token_and_issues_child(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)

        rotation = await _rotate(factory, r0)

        assert rotation.admin.id == admin_id
        assert rotation.session_id == session_id
        assert rotation.raw_token != r0
        consumed = await _token(factory, r0)
        child = await _token(factory, rotation.raw_token)
        assert consumed.consumed_at is not None
        assert consumed.revoked_at is None
        assert child.generation == 1
        assert child.session_id == session_id
        assert (await _session(factory, session_id)).current_generation == 1

    async def test_rotation_slides_token_expiry_not_session_expiry(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        absolute = (await _session(factory, session_id)).absolute_expires_at
        await _set_token_expiry(factory, r0, datetime.now(UTC) + timedelta(hours=1))

        r1 = (await _rotate(factory, r0)).raw_token

        child = await _token(factory, r1)
        assert _close(
            child.expires_at,
            datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        )
        after = await _session(factory, session_id)
        assert after.absolute_expires_at == absolute
        assert after.last_refresh_at is not None

    async def test_child_never_outlives_the_session(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        absolute = datetime.now(UTC) + timedelta(days=1)
        await _set_absolute_expiry(factory, session_id, absolute)

        r1 = (await _rotate(factory, r0)).raw_token

        assert _close((await _token(factory, r1)).expires_at, absolute)

    async def test_unknown_token_is_invalid(self, factory: Factory) -> None:
        assert await _rotate_error(factory, "never-issued") == "INVALID_TOKEN"


# =============================================================================
# Lost answers and replay
# =============================================================================


class TestLostAnswerRecovery:
    async def test_parent_again_gets_a_sibling_and_keeps_the_successor(
        self, factory: Factory
    ) -> None:
        """R0 -> R1 whose answer was lost: R0 again gets a sibling of R1."""
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        r1 = (await _rotate(factory, r0)).raw_token
        first_consumed = (await _token(factory, r0)).consumed_at

        sibling = (await _rotate(factory, r0)).raw_token

        assert sibling not in (r0, r1)
        assert (await _token(factory, r0)).consumed_at == first_consumed
        live = _live(await _tokens(factory, session_id))
        assert {t.token_hash for t in live} == {_hash(r1), _hash(sibling)}
        assert {t.generation for t in live} == {1}
        auth_session = await _session(factory, session_id)
        assert auth_session.revoked_at is None
        assert auth_session.current_generation == 1

    async def test_using_the_successor_kills_the_sibling(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        r1 = (await _rotate(factory, r0)).raw_token
        sibling = (await _rotate(factory, r0)).raw_token

        r2 = (await _rotate(factory, r1)).raw_token

        killed = await _token(factory, sibling)
        assert killed.revoked_at is not None
        live = _live(await _tokens(factory, session_id))
        assert [t.token_hash for t in live] == [_hash(r2)]

        # Presenting the killed sibling is a replay: the session ends.
        assert await _rotate_error(factory, sibling) == "TOKEN_REVOKED"
        auth_session = await _session(factory, session_id)
        assert auth_session.revoked_at is not None
        assert auth_session.revoked_reason == "replay"
        assert _live(await _tokens(factory, session_id)) == []

    async def test_sibling_cap_ends_the_session(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        _ = await _rotate(factory, r0)
        for _attempt in range(MAX_LIVE_TOKENS_PER_SESSION - 1):
            _ = await _rotate(factory, r0)
        assert len(_live(await _tokens(factory, session_id))) == (
            MAX_LIVE_TOKENS_PER_SESSION
        )

        assert await _rotate_error(factory, r0) == "TOKEN_REVOKED"
        auth_session = await _session(factory, session_id)
        assert auth_session.revoked_reason == "replay"
        assert _live(await _tokens(factory, session_id)) == []

    async def test_no_recovery_once_the_successor_would_have_expired(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        _ = await _rotate(factory, r0)
        async with factory() as session:
            _ = await session.execute(
                update(RefreshToken)
                .where(RefreshToken.token_hash == _hash(r0))
                .values(
                    consumed_at=datetime.now(UTC)
                    - timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS, minutes=1)
                )
            )
            await session.commit()

        assert await _rotate_error(factory, r0) == "TOKEN_EXPIRED"
        assert (await _session(factory, session_id)).revoked_reason == "expired"


class TestReplay:
    async def test_grandparent_replay_revokes_the_session(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        r1 = (await _rotate(factory, r0)).raw_token
        r2 = (await _rotate(factory, r1)).raw_token

        assert await _rotate_error(factory, r0) == "TOKEN_REVOKED"

        auth_session = await _session(factory, session_id)
        assert auth_session.revoked_at is not None
        assert auth_session.revoked_reason == "replay"
        assert (await _token(factory, r2)).revoked_at is not None
        assert await _rotate_error(factory, r2) == "TOKEN_REVOKED"

    async def test_replay_on_a_revoked_session_writes_nothing(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        r1 = (await _rotate(factory, r0)).raw_token
        _ = await _rotate(factory, r1)
        assert await _rotate_error(factory, r0) == "TOKEN_REVOKED"

        def snapshot(
            auth_session: AuthSession, tokens: list[RefreshToken]
        ) -> tuple[object, ...]:
            return (
                auth_session.revoked_at,
                auth_session.revoked_reason,
                auth_session.last_refresh_at,
                auth_session.current_generation,
                tuple((t.id, t.consumed_at, t.revoked_at) for t in tokens),
            )

        before = snapshot(
            await _session(factory, session_id), await _tokens(factory, session_id)
        )
        for raw in (r0, r1):
            assert await _rotate_error(factory, raw) == "TOKEN_REVOKED"
        after = snapshot(
            await _session(factory, session_id), await _tokens(factory, session_id)
        )
        assert after == before

    async def test_replay_leaves_other_sessions_of_the_admin_alone(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_x, x0 = await _start(factory, admin_id)
        session_y, y0 = await _start(factory, admin_id)
        x1 = (await _rotate(factory, x0)).raw_token
        _ = await _rotate(factory, x1)

        assert await _rotate_error(factory, x0) == "TOKEN_REVOKED"

        assert (await _session(factory, session_x)).revoked_at is not None
        assert (await _session(factory, session_y)).revoked_at is None
        rotation = await _rotate(factory, y0)
        assert rotation.session_id == session_y

    async def test_expired_token_ends_the_session(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        await _set_token_expiry(factory, r0, datetime.now(UTC) - timedelta(minutes=1))

        assert await _rotate_error(factory, r0) == "TOKEN_EXPIRED"

        auth_session = await _session(factory, session_id)
        assert auth_session.revoked_reason == "expired"
        assert _live(await _tokens(factory, session_id)) == []

    async def test_session_past_its_absolute_expiry_refuses_refresh(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        await _set_absolute_expiry(
            factory, session_id, datetime.now(UTC) - timedelta(minutes=1)
        )

        assert await _rotate_error(factory, r0) == "TOKEN_REVOKED"
        assert (await _token(factory, r0)).consumed_at is None

    async def test_rotation_returns_a_disabled_admin_for_the_caller_to_refuse(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory, enabled=False)
        _session_id, r0 = await _start(factory, admin_id)

        rotation = await _rotate(factory, r0)

        assert rotation.admin.enabled is False


# =============================================================================
# end_session
# =============================================================================


class TestEndSession:
    async def test_by_refresh_token(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        other_id, _other = await _start(factory, admin_id)

        assert await _end(factory, raw=r0) is True

        ended = await _session(factory, session_id)
        assert ended.revoked_reason == "logout"
        assert (await _token(factory, r0)).revoked_at is not None
        assert (await _session(factory, other_id)).revoked_at is None
        assert await _rotate_error(factory, r0) == "TOKEN_REVOKED"

    async def test_by_session_id_and_twice(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)

        assert await _end(factory, session_id=session_id) is True
        assert await _end(factory, session_id=session_id) is False
        assert await _end(factory, raw=r0) is False

        assert (await _session(factory, session_id)).revoked_reason == "logout"

    async def test_unknown_refresh_token_falls_back_to_session_id(
        self, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        session_id, _r0 = await _start(factory, admin_id)

        assert await _end(factory, raw="unknown", session_id=session_id) is True
        assert await _end(factory, raw="unknown") is False


# =============================================================================
# Concurrency: independent connections
# =============================================================================


class TestConcurrency:
    async def test_parallel_rotations_of_one_token_both_succeed(
        self, factory: Factory
    ) -> None:
        """Two tabs refresh R0 at once: one rotates, the other recovers."""
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)

        first, second = await asyncio.gather(_rotate(factory, r0), _rotate(factory, r0))

        assert first.raw_token != second.raw_token
        tokens = await _tokens(factory, session_id)
        consumed = [t for t in tokens if t.consumed_at is not None]
        assert [t.token_hash for t in consumed] == [_hash(r0)]
        live = _live(tokens)
        assert {t.token_hash for t in live} == {
            _hash(first.raw_token),
            _hash(second.raw_token),
        }
        assert {t.generation for t in live} == {1}
        auth_session = await _session(factory, session_id)
        assert auth_session.current_generation == 1
        assert auth_session.revoked_at is None

    async def test_rotation_racing_a_replay_leaves_no_live_successor(
        self, factory: Factory
    ) -> None:
        """Finding 4: a successor issued concurrently with a replay must not survive."""
        admin_id = await _create_admin(factory)
        for _round in range(5):
            session_id, r0 = await _start(factory, admin_id)
            r1 = (await _rotate(factory, r0)).raw_token
            r2 = (await _rotate(factory, r1)).raw_token

            outcomes = await asyncio.gather(
                _rotate(factory, r2), _rotate(factory, r0), return_exceptions=True
            )

            replay = outcomes[1]
            assert isinstance(replay, AuthenticationError)
            assert replay.error_code == "TOKEN_REVOKED"
            current = outcomes[0]
            if isinstance(current, Rotation):
                assert await _rotate_error(factory, current.raw_token) == (
                    "TOKEN_REVOKED"
                )
            else:
                assert isinstance(current, AuthenticationError)
                assert current.error_code == "TOKEN_REVOKED"
            assert (await _session(factory, session_id)).revoked_at is not None
            assert _live(await _tokens(factory, session_id)) == []


# =============================================================================
# Cleanup task
# =============================================================================


class TestCleanup:
    async def test_deletes_only_sessions_that_are_over(self, factory: Factory) -> None:
        admin_id = await _create_admin(factory)
        now = datetime.now(UTC)
        live_id, _live_raw = await _start(factory, admin_id)
        absolute_id, _ = await _start(factory, admin_id)
        await _set_absolute_expiry(factory, absolute_id, now - timedelta(minutes=1))
        idle_id, idle_raw = await _start(factory, admin_id)
        await _set_token_expiry(factory, idle_raw, now - timedelta(minutes=1))
        recent_id, recent_raw = await _start(factory, admin_id)
        assert await _end(factory, raw=recent_raw)
        old_id, old_raw = await _start(factory, admin_id)
        assert await _end(factory, raw=old_raw)
        async with factory() as session:
            _ = await session.execute(
                update(AuthSession)
                .where(AuthSession.id == old_id)
                .values(revoked_at=now - timedelta(days=8))
            )
            await session.commit()

        manager = BackgroundTaskManager(Settings(secret_key=CLEANUP_SECRET_KEY))
        await manager.cleanup_expired_tokens(State({"session_factory": factory}))

        async with factory() as session:
            remaining = set(await session.scalars(select(AuthSession.id)))
            token_sessions = set(await session.scalars(select(RefreshToken.session_id)))
        assert remaining == {live_id, recent_id}
        assert token_sessions == {live_id, recent_id}
        assert idle_id not in remaining

    async def test_cleanup_racing_a_rotation_keeps_the_rotated_session(
        self, factory: Factory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cleanup that waited on a rotation's session lock re-checks it afterwards.

        On PostgreSQL the test waits until cleanup is blocked on the lock
        (``pg_stat_activity``), so the interleaving is the same on every run.

        The rotation holds the session lock while cleanup decides; at cleanup's
        ``now`` the only token it can see (R0, not yet consumed for it) has
        expired, so the session looks stale. Once the rotation commits R1, the
        session has a live token again and must survive.
        """
        async with factory() as probe:
            postgres = probe.get_bind().dialect.name == "postgresql"
        admin_id = await _create_admin(factory)
        session_id, r0 = await _start(factory, admin_id)
        r0_expiry = datetime.now(UTC) + timedelta(hours=1)
        await _set_token_expiry(factory, r0, r0_expiry)
        cleanup_now = r0_expiry + timedelta(seconds=1)

        locked = asyncio.Event()
        release = asyncio.Event()
        issue = AuthService._issue_token  # pyright: ignore[reportPrivateUsage]

        async def paused_issue(
            self: AuthService,
            auth_session: AuthSession,
            *,
            generation: int,
            now: datetime,
        ) -> str:
            locked.set()
            _ = await release.wait()
            return await issue(self, auth_session, generation=generation, now=now)

        monkeypatch.setattr(AuthService, "_issue_token", paused_issue)

        async def cleanup() -> int:
            async with factory() as session:
                deleted = await AuthSessionRepository(session).delete_stale(
                    cleanup_now, revoked_before=cleanup_now - timedelta(days=7)
                )
                await session.commit()
                return deleted

        async def waiting_on_locks() -> int:
            async with factory() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(text("pg_stat_activity"))
                    .where(
                        text(
                            "datname = current_database() AND wait_event_type = 'Lock'"
                        )
                    )
                )
                return result.scalar_one()

        rotation_task = asyncio.create_task(_rotate(factory, r0))
        _ = await asyncio.wait_for(locked.wait(), timeout=10)
        cleanup_task = asyncio.create_task(cleanup())
        if postgres:
            async with asyncio.timeout(10):
                while await waiting_on_locks() == 0:
                    await asyncio.sleep(0.02)
        else:
            # SQLite has no lock view; cleanup still running while the rotation
            # holds the write lock means its DELETE is waiting for it.
            await asyncio.sleep(0.5)
        assert not cleanup_task.done()
        release.set()

        rotation = await rotation_task
        assert await cleanup_task == 0
        assert (await _session(factory, session_id)).revoked_at is None
        assert _live(await _tokens(factory, session_id))[0].token_hash == _hash(
            rotation.raw_token
        )
