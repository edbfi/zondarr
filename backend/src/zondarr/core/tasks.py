"""Background task management for Zondarr.

Provides:
- BackgroundTaskManager: Manages periodic background tasks
- background_tasks_lifespan: Lifespan context manager for task lifecycle

Background tasks include:
- Invitation expiration: Disables expired invitation codes
- Media server sync: Synchronizes user data with connected servers

Uses asyncio tasks with graceful shutdown support.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import structlog
from litestar import Litestar
from litestar.datastructures import State
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zondarr.api.schemas import SyncResult
from zondarr.config import Settings
from zondarr.core.retry import (
    CircuitBreakerRegistry,
    RetryPolicy,
    is_retryable_sync_error,
)
from zondarr.models.sync_run import SyncRun
from zondarr.repositories.admin import AuthSessionRepository
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.sync_run import SyncRunRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.auth import REVOKED_SESSION_RETENTION_DAYS
from zondarr.services.media_server import MediaServerService
from zondarr.services.oauth_session import OAuthSessionStore
from zondarr.services.sync import SyncService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]


class BackgroundTaskManager:
    """Manages periodic background tasks for Zondarr.

    Runs invitation expiration checks and media server synchronization
    at configurable intervals using asyncio tasks.

    Attributes:
        settings: Application settings containing task intervals.
    """

    _tasks: list[asyncio.Task[None]]
    _running: bool
    _next_sync_run_at: datetime | None
    _libraries_sync_in_progress: set[UUID]
    _users_sync_in_progress: set[UUID]
    _retry_policy: RetryPolicy
    _circuit_registry: CircuitBreakerRegistry
    settings: Settings

    def __init__(self, settings: Settings, /) -> None:
        """Initialize the BackgroundTaskManager.

        Args:
            settings: Application settings with task intervals (positional-only).
        """
        self._tasks = []
        self._running = False
        self._next_sync_run_at = None
        self._libraries_sync_in_progress = set()
        self._users_sync_in_progress = set()
        self._retry_policy = RetryPolicy(
            max_retries=settings.sync_max_retries,
            backoff_base=settings.sync_backoff_base_seconds,
        )
        self._circuit_registry = CircuitBreakerRegistry()
        self.settings = settings

    async def start(self, state: State, /) -> None:
        """Start all background tasks.

        Creates asyncio tasks for expiration checking and media server sync.
        Tasks run continuously until stop() is called.

        Args:
            state: Application state containing session factory (positional-only).
        """
        self._running = True

        self._tasks.append(
            asyncio.create_task(
                self._run_expiration_task(state),
                name="invitation-expiration",
            )
        )
        self._tasks.append(
            asyncio.create_task(
                self._run_sync_task(state),
                name="media-server-sync",
            )
        )
        self._tasks.append(
            asyncio.create_task(
                self._run_token_cleanup_task(state),
                name="token-cleanup",
            )
        )
        self._tasks.append(
            asyncio.create_task(
                self._run_oauth_cleanup_task(state),
                name="oauth-session-cleanup",
            )
        )

        logger.info("Background tasks started")

    async def stop(self) -> None:
        """Stop all background tasks gracefully.

        Cancels all running tasks and waits for them to complete
        within a timeout. Exceptions from cancelled tasks are suppressed.
        """
        self._running = False

        for task in self._tasks:
            _ = task.cancel()

        if self._tasks:
            try:
                _ = await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=10.0,
                )
            except TimeoutError:
                logger.warning(
                    "Background tasks did not stop within timeout",
                    remaining_tasks=len([t for t in self._tasks if not t.done()]),
                )

        self._tasks.clear()
        self._next_sync_run_at = None
        self._libraries_sync_in_progress.clear()
        self._users_sync_in_progress.clear()

        logger.info("Background tasks stopped")

    def get_next_sync_run_at(self) -> datetime | None:
        """Return next scheduled automatic sync timestamp, if available."""
        return self._next_sync_run_at

    def is_libraries_sync_in_progress(self, server_id: UUID, /) -> bool:
        """Return whether a library sync is currently running for a server."""
        return server_id in self._libraries_sync_in_progress

    def is_users_sync_in_progress(self, server_id: UUID, /) -> bool:
        """Return whether a user sync is currently running for a server."""
        return server_id in self._users_sync_in_progress

    def get_circuit_state(
        self, server_id: UUID, /
    ) -> tuple[str, int, datetime | None] | None:
        """Return circuit breaker state for a media server.

        Args:
            server_id: UUID of the media server (positional-only).

        Returns:
            A tuple of ``(state, consecutive_failures, next_attempt_at)`` or
            ``None`` if no breaker exists for the given server.
        """
        return self._circuit_registry.get_state(server_id)

    def reset_circuit_breaker(self, server_id: UUID, /) -> None:
        """Manually reset the circuit breaker for a media server to CLOSED.

        Args:
            server_id: UUID of the media server (positional-only).
        """
        self._circuit_registry.reset(server_id)

    async def _run_expiration_task(self, state: State, /) -> None:
        """Periodically check and disable expired invitations.

        Runs at the interval specified by expiration_check_interval_seconds.
        Errors are logged but don't stop the task from continuing.

        Args:
            state: Application state containing session factory (positional-only).
        """
        interval = self.settings.expiration_check_interval_seconds

        while self._running:
            try:
                await self._check_expired_invitations(state)
            except Exception as exc:
                logger.exception("Expiration task error", exc_info=exc)

            await asyncio.sleep(interval)

    async def _run_sync_task(self, state: State, /) -> None:
        """Periodically sync users with media servers.

        Runs at the interval specified by sync_interval_seconds.
        Errors are logged but don't stop the task from continuing.

        Args:
            state: Application state containing session factory (positional-only).
        """
        interval = max(self.settings.sync_interval_seconds, 60)

        # Delay initial sync to avoid blocking web requests at startup,
        # especially important for SQLite's single-writer limitation
        self._next_sync_run_at = datetime.now(UTC) + timedelta(seconds=15)
        await asyncio.sleep(15)

        while self._running:
            try:
                self._next_sync_run_at = None
                await self._sync_all_servers(state)
            except Exception as exc:
                logger.exception("Sync task error", exc_info=exc)

            self._next_sync_run_at = datetime.now(UTC) + timedelta(seconds=interval)
            await asyncio.sleep(interval)

    async def check_expired_invitations(self, state: State, /) -> None:
        """Check for and disable expired invitations.

        Public method for testing. Delegates to internal implementation.

        Args:
            state: Application state containing session factory (positional-only).
        """
        await self._check_expired_invitations(state)

    async def sync_all_servers(self, state: State, /) -> None:
        """Sync users with all enabled media servers.

        Public method for testing. Delegates to internal implementation.

        Args:
            state: Application state containing session factory (positional-only).
        """
        await self._sync_all_servers(state)

    async def _check_expired_invitations(self, state: State, /) -> None:
        """Check for and disable expired invitations.

        Queries all expired but enabled invitations and disables them.
        Individual errors are logged but don't stop processing of remaining
        invitations.

        Args:
            state: Application state containing session factory (positional-only).
        """
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        async with session_factory() as session:
            repo = InvitationRepository(session)

            now = datetime.now(UTC)
            expired = await repo.get_expired(now)

            disabled_count = 0
            for invitation in expired:
                try:
                    if invitation.enabled:
                        invitation.enabled = False
                        _ = await repo.update(invitation)
                        disabled_count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to disable expired invitation",
                        invitation_id=str(invitation.id),
                        error=str(exc),
                    )

            if disabled_count > 0:
                await session.commit()
                logger.info(
                    "Disabled expired invitations",
                    count=disabled_count,
                    checked_at=now.isoformat(),
                )

    async def _sync_all_servers(self, state: State, /) -> None:
        """Sync users with all enabled media servers.

        Uses short-lived sessions per operation to avoid holding SQLite's
        write lock during external API calls (which can take several seconds).
        Individual server failures are logged but don't stop processing
        of remaining servers.

        Each server has a shared circuit breaker across library and user phases.
        If library sync opens the circuit, user sync is also skipped.
        Retries use exponential backoff with jitter via the configured RetryPolicy.

        Args:
            state: Application state containing session factory (positional-only).
        """
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        # Fetch enabled servers with a short-lived session
        async with session_factory() as session:
            server_repo = MediaServerRepository(session)
            servers = await server_repo.get_enabled()
            # Detach server data before closing session
            server_ids_and_names = [(s.id, s.name) for s in servers]

        timeout = self.settings.sync_per_server_timeout_seconds
        failure_threshold = self.settings.sync_circuit_failure_threshold
        recovery_seconds = self.settings.sync_circuit_recovery_seconds

        # Mutable counter tracking the number of retries performed by the
        # current ``_retry_policy.execute()`` call.  Reset before each call;
        # the ``_on_retry`` callback increments it so the error message
        # reports the *actual* attempt count instead of ``max_retries + 1``.
        retry_count: list[int] = [0]

        def _on_retry(attempt: int, delay: float, exc: Exception) -> None:
            retry_count[0] += 1
            logger.info(
                "sync_retry",
                attempt=attempt + 1,
                max_retries=self._retry_policy.max_retries,
                delay=round(delay, 3),
                error=str(exc),
            )

        # Sync libraries per server, each with its own session
        for server_id, server_name in server_ids_and_names:
            # Yield to event loop between servers so HTTP requests
            # are not starved while sync holds SQLite write locks
            await asyncio.sleep(0)

            breaker = self._circuit_registry.get_or_create(
                server_id,
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_seconds,
            )

            if not breaker.should_allow():
                await self._record_sync_run(
                    state,
                    media_server_id=server_id,
                    sync_type="libraries",
                    trigger="automatic",
                    status="failed",
                    started_at=datetime.now(UTC),
                    error_message=(
                        f"Circuit breaker open after {breaker.consecutive_failures}"
                        " consecutive failures"
                    ),
                )
                logger.warning(
                    "sync_skipped_circuit_open",
                    server_id=str(server_id),
                    server_name=server_name,
                    sync_type="libraries",
                    consecutive_failures=breaker.consecutive_failures,
                )
                continue

            started_at = datetime.now(UTC)
            self._libraries_sync_in_progress.add(server_id)
            retry_count[0] = 0
            try:
                await self._retry_policy.execute(
                    lambda sid=server_id: asyncio.wait_for(
                        self._sync_server_libraries(session_factory, sid),
                        timeout=timeout,
                    ),
                    is_retryable=is_retryable_sync_error,
                    on_retry=_on_retry,
                )
                breaker.record_success()
                await self._record_sync_run(
                    state,
                    media_server_id=server_id,
                    sync_type="libraries",
                    trigger="automatic",
                    status="success",
                    started_at=started_at,
                )
                logger.info(
                    "Library sync completed",
                    server_id=str(server_id),
                    server_name=server_name,
                )
            except Exception as exc:
                breaker.record_failure()
                error_message = (
                    f"Timed out after {timeout}s"
                    if isinstance(exc, TimeoutError)
                    else str(exc)
                )
                await self._record_sync_run(
                    state,
                    media_server_id=server_id,
                    sync_type="libraries",
                    trigger="automatic",
                    status="failed",
                    started_at=started_at,
                    error_message=(
                        f"Failed after {retry_count[0] + 1} attempt(s): {error_message}"
                    ),
                )
                logger.warning(
                    "Library sync failed",
                    server_id=str(server_id),
                    server_name=server_name,
                    error=error_message,
                )
            finally:
                self._libraries_sync_in_progress.discard(server_id)

        # Yield between library sync and user sync phases
        await asyncio.sleep(0)

        # Sync users per server, each with its own session
        for server_id, server_name in server_ids_and_names:
            # Yield to event loop between servers
            await asyncio.sleep(0)

            breaker = self._circuit_registry.get_or_create(
                server_id,
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_seconds,
            )

            if not breaker.should_allow():
                await self._record_sync_run(
                    state,
                    media_server_id=server_id,
                    sync_type="users",
                    trigger="automatic",
                    status="failed",
                    started_at=datetime.now(UTC),
                    error_message=(
                        f"Circuit breaker open after {breaker.consecutive_failures}"
                        " consecutive failures"
                    ),
                )
                logger.warning(
                    "sync_skipped_circuit_open",
                    server_id=str(server_id),
                    server_name=server_name,
                    sync_type="users",
                    consecutive_failures=breaker.consecutive_failures,
                )
                continue

            started_at = datetime.now(UTC)
            self._users_sync_in_progress.add(server_id)
            retry_count[0] = 0
            try:
                result = await self._retry_policy.execute(
                    lambda sid=server_id: asyncio.wait_for(
                        self._sync_server_users(session_factory, sid),
                        timeout=timeout,
                    ),
                    is_retryable=is_retryable_sync_error,
                    on_retry=_on_retry,
                )
                breaker.record_success()
                await self._record_sync_run(
                    state,
                    media_server_id=server_id,
                    sync_type="users",
                    trigger="automatic",
                    status="success",
                    started_at=started_at,
                )
                logger.info(
                    "Server sync completed",
                    server_id=str(server_id),
                    server_name=server_name,
                    orphaned=len(result.orphaned_users),
                    stale=len(result.stale_users),
                    matched=result.matched_users,
                    imported=result.imported_users,
                )
            except Exception as exc:
                breaker.record_failure()
                error_message = (
                    f"Timed out after {timeout}s"
                    if isinstance(exc, TimeoutError)
                    else str(exc)
                )
                await self._record_sync_run(
                    state,
                    media_server_id=server_id,
                    sync_type="users",
                    trigger="automatic",
                    status="failed",
                    started_at=started_at,
                    error_message=(
                        f"Failed after {retry_count[0] + 1} attempt(s): {error_message}"
                    ),
                )
                logger.warning(
                    "Server sync failed",
                    server_id=str(server_id),
                    server_name=server_name,
                    error=error_message,
                )
            finally:
                self._users_sync_in_progress.discard(server_id)

    async def _sync_server_libraries(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        server_id: UUID,
    ) -> None:
        """Sync libraries for a single server (awaitable for wait_for)."""
        async with session_factory() as session:
            server_repo = MediaServerRepository(session)
            media_server_service = MediaServerService(server_repo)
            _ = await media_server_service.sync_libraries(server_id)
            await session.commit()

    async def _sync_server_users(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        server_id: UUID,
    ) -> SyncResult:
        """Sync users for a single server (awaitable for wait_for)."""
        async with session_factory() as session:
            server_repo = MediaServerRepository(session)
            user_repo = UserRepository(session)
            identity_repo = IdentityRepository(session)
            sync_service = SyncService(
                server_repo,
                user_repo,
                identity_repo,
            )
            result = await sync_service.sync_server(server_id, dry_run=False)
            await session.commit()
        return result

    async def _record_sync_run(
        self,
        state: State,
        /,
        *,
        media_server_id: UUID,
        sync_type: str,
        trigger: str,
        status: str,
        started_at: datetime,
        error_message: str | None = None,
    ) -> None:
        """Persist a sync run record in a dedicated short-lived session."""
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )
        finished_at = datetime.now(UTC)

        try:
            async with session_factory() as session:
                repo = SyncRunRepository(session)
                _ = await repo.create(
                    SyncRun(
                        media_server_id=media_server_id,
                        sync_type=sync_type,
                        trigger=trigger,
                        status=status,
                        started_at=started_at,
                        finished_at=finished_at,
                        error_message=error_message,
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "Failed to persist sync run record",
                media_server_id=str(media_server_id),
                sync_type=sync_type,
                trigger=trigger,
                status=status,
                error=str(exc),
            )

    async def _run_token_cleanup_task(self, state: State, /) -> None:
        """Periodically clean up auth sessions that are over, with their tokens.

        Runs at the same interval as expiration checks.
        """
        interval = self.settings.expiration_check_interval_seconds

        while self._running:
            try:
                await self._cleanup_expired_tokens(state)
            except Exception as exc:
                logger.exception("Token cleanup task error", exc_info=exc)

            await asyncio.sleep(interval)

    async def cleanup_expired_tokens(self, state: State, /) -> None:
        """Delete stale auth sessions and their refresh tokens.

        Public method for testing. Delegates to internal implementation.

        Args:
            state: Application state containing session factory (positional-only).
        """
        await self._cleanup_expired_tokens(state)

    async def _cleanup_expired_tokens(self, state: State, /) -> None:
        """Delete auth sessions that are over, and their refresh tokens.

        A session is deleted once past its absolute expiry, once it has no
        live refresh token that has not expired, or, when revoked, after the
        audit retention period.
        """
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        async with session_factory() as session:
            repo = AuthSessionRepository(session)
            now = datetime.now(UTC)
            deleted = await repo.delete_stale(
                now,
                revoked_before=now - timedelta(days=REVOKED_SESSION_RETENTION_DAYS),
            )
            await session.commit()
            if deleted > 0:
                logger.info("Cleaned up stale auth sessions", count=deleted)

    async def _run_oauth_cleanup_task(self, state: State, /) -> None:
        """Periodically clean up expired OAuth sessions.

        Runs at the same interval as expiration checks.
        """
        interval = self.settings.expiration_check_interval_seconds

        while self._running:
            try:
                await self._cleanup_expired_oauth_sessions(state)
            except Exception as exc:
                logger.exception("OAuth session cleanup task error", exc_info=exc)

            await asyncio.sleep(interval)

    async def _cleanup_expired_oauth_sessions(self, state: State, /) -> None:
        """Remove expired OAuth sessions from the database."""
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        async with session_factory() as session:
            store = OAuthSessionStore()
            await store.cleanup_expired(session)
            await session.commit()


@asynccontextmanager
async def background_tasks_lifespan(app: Litestar):
    """Lifespan context manager for background tasks.

    Starts background tasks on application startup and stops them
    gracefully on shutdown.

    Args:
        app: The Litestar application instance.

    Yields:
        None - tasks are managed internally.
    """
    settings = cast(Settings, app.state.settings)
    manager = BackgroundTaskManager(settings)
    app.state.background_task_manager = manager

    await manager.start(app.state)

    try:
        yield
    finally:
        await manager.stop()
