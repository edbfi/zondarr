"""Repositories for admin authentication entities."""

from datetime import datetime
from typing import override
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, exists, func, insert, literal, or_, select, update
from sqlalchemy.exc import IntegrityError

from zondarr.core.exceptions import RepositoryError
from zondarr.models.admin import AdminAccount, AuthSession, RefreshToken
from zondarr.repositories.base import Repository


def _rowcount(result: object) -> int:
    """Rows matched by an UPDATE/DELETE (``Result`` does not type ``rowcount``)."""
    rowcount: object = getattr(result, "rowcount", 0)
    return rowcount if isinstance(rowcount, int) else 0


class AdminAccountRepository(Repository[AdminAccount]):
    """Repository for AdminAccount CRUD operations."""

    @property
    @override
    def _model_class(self) -> type[AdminAccount]:
        return AdminAccount

    async def get_by_username(self, username: str) -> AdminAccount | None:
        """Find an admin account by username.

        Args:
            username: The username to search for.

        Returns:
            The AdminAccount if found, None otherwise.
        """
        try:
            stmt = select(AdminAccount).where(AdminAccount.username == username)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get AdminAccount by username",
                operation="get_by_username",
                original=e,
            ) from e

    async def get_by_external_id(
        self, external_id: str, auth_method: str
    ) -> AdminAccount | None:
        """Find an admin account by external ID and auth method.

        Args:
            external_id: The external service identifier.
            auth_method: The authentication method (plex/jellyfin).

        Returns:
            The AdminAccount if found, None otherwise.
        """
        try:
            stmt = select(AdminAccount).where(
                AdminAccount.external_id == external_id,
                AdminAccount.auth_method == auth_method,
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get AdminAccount by external_id",
                operation="get_by_external_id",
                original=e,
            ) from e

    async def count(self) -> int:
        """Count total admin accounts.

        Returns:
            The number of admin accounts in the database.
        """
        try:
            stmt = select(func.count()).select_from(AdminAccount)
            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            raise RepositoryError(
                "Failed to count AdminAccounts",
                operation="count",
                original=e,
            ) from e

    async def consume_challenge_nonce(self, admin_id: UUID, nonce: str) -> bool:
        """Atomically consume a TOTP challenge nonce.

        Uses a conditional UPDATE to ensure the nonce matches the expected
        value. If the nonce was already consumed by a concurrent request,
        rowcount will be 0 and we return False. This prevents TOCTOU races
        where two parallel requests could both observe the same nonce.

        Args:
            admin_id: The UUID of the admin account.
            nonce: The expected nonce value to consume.

        Returns:
            True if the nonce was consumed, False if it was already
            consumed or didn't match.
        """
        try:
            stmt = (
                update(AdminAccount)
                .where(
                    AdminAccount.id == admin_id,
                    AdminAccount.totp_challenge_nonce == nonce,
                )
                .values(totp_challenge_nonce=None)
            )
            result = await self.session.execute(stmt)
            return result.rowcount > 0  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        except Exception as e:
            raise RepositoryError(
                "Failed to consume challenge nonce",
                operation="consume_challenge_nonce",
                original=e,
            ) from e

    async def create_first_admin(
        self,
        *,
        username: str,
        password_hash: str,
        email: str | None,
        auth_method: str,
    ) -> AdminAccount | None:
        """Create the first admin account if none exists.

        Uses INSERT ... SELECT ... WHERE NOT EXISTS as the primary guard.
        Falls back to catching IntegrityError from the UNIQUE constraint
        on ``username`` to handle PostgreSQL races under READ COMMITTED
        isolation (two transactions can both see "no rows" and attempt
        to insert). A savepoint keeps the outer transaction clean.

        The caller (AuthService.setup_admin) also holds an asyncio.Lock
        to serialize attempts within a single process.

        Args:
            username: Admin username.
            password_hash: Pre-hashed password.
            email: Optional email address.
            auth_method: Authentication method (e.g. "local").

        Returns:
            The created AdminAccount, or None if an admin already exists.
        """
        try:
            admin_id = uuid4()
            columns = [
                AdminAccount.__table__.c.id,
                AdminAccount.__table__.c.username,
                AdminAccount.__table__.c.password_hash,
                AdminAccount.__table__.c.email,
                AdminAccount.__table__.c.auth_method,
                AdminAccount.__table__.c.enabled,
            ]
            values = select(
                literal(admin_id.hex).label("id"),
                literal(username).label("username"),
                literal(password_hash).label("password_hash"),
                literal(email).label("email"),
                literal(auth_method).label("auth_method"),
                literal(True).label("enabled"),
            ).where(~exists(select(AdminAccount.id)))

            table = AdminAccount.__table__
            stmt = insert(table).from_select(columns, values)  # pyright: ignore[reportArgumentType]
            result = await self.session.execute(stmt)

            if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                return None

            return await self.get_by_id(admin_id)
        except IntegrityError:
            # Concurrent insert won the race — UNIQUE(username) prevented
            # the duplicate. The caller (setup_admin) will raise
            # AuthenticationError, and the DI layer rolls back the session.
            return None
        except Exception as e:
            raise RepositoryError(
                "Failed to create first admin",
                operation="create_first_admin",
                original=e,
            ) from e


class AuthSessionRepository(Repository[AuthSession]):
    """Repository for AuthSession rows (one per sign-in)."""

    @property
    @override
    def _model_class(self) -> type[AuthSession]:
        return AuthSession

    async def lock(self, session_id: UUID, now: datetime) -> bool:
        """Take the session's write lock by touching ``last_refresh_at``.

        Must be the transaction's first write. On PostgreSQL the UPDATE
        row-locks the session until commit, so rotations and revocations of
        one session run one after the other. On SQLite (pysqlite's implicit
        transactions: plain SELECTs open none) it begins the transaction and
        takes the database write lock with no older read snapshot, so the
        busy timeout waits for a concurrent writer instead of failing.

        Args:
            session_id: The session to lock.
            now: Current UTC datetime.

        Returns:
            True if the session exists, False otherwise.
        """
        try:
            stmt = (
                update(AuthSession)
                .where(AuthSession.id == session_id)
                .values(last_refresh_at=now)
                .execution_options(synchronize_session=False)
            )
            result = await self.session.execute(stmt)
            return _rowcount(result) > 0
        except Exception as e:
            raise RepositoryError(
                "Failed to lock AuthSession",
                operation="lock",
                original=e,
            ) from e

    async def get_current(self, session_id: UUID) -> AuthSession | None:
        """Read a session as committed now, replacing any cached copy.

        Args:
            session_id: The session to read.

        Returns:
            The AuthSession if found, None otherwise.
        """
        try:
            stmt = (
                select(AuthSession)
                .where(AuthSession.id == session_id)
                .execution_options(populate_existing=True)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get AuthSession",
                operation="get_current",
                original=e,
            ) from e

    async def revoke(self, session_id: UUID, *, reason: str, now: datetime) -> bool:
        """Revoke a session and every live refresh token it has.

        The session UPDATE comes first, so it takes the session's lock before
        any token row (the order rotation uses too). Revoking a session that
        is already revoked changes nothing.

        Args:
            session_id: The session to revoke.
            reason: Why (logout, replay, expired, admin).
            now: Current UTC datetime.

        Returns:
            True if this call revoked the session, False if it was already
            revoked or does not exist.
        """
        try:
            session_stmt = (
                update(AuthSession)
                .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now, revoked_reason=reason)
                .execution_options(synchronize_session=False)
            )
            result = await self.session.execute(session_stmt)
            revoked = _rowcount(result) > 0
            tokens_stmt = (
                update(RefreshToken)
                .where(
                    RefreshToken.session_id == session_id,
                    RefreshToken.consumed_at.is_(None),
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
                .execution_options(synchronize_session=False)
            )
            _ = await self.session.execute(tokens_stmt)
            return revoked
        except Exception as e:
            raise RepositoryError(
                "Failed to revoke AuthSession",
                operation="revoke",
                original=e,
            ) from e

    async def get_with_admin(
        self, admin_id: UUID, session_id: UUID
    ) -> tuple[AdminAccount, AuthSession] | None:
        """Load an admin together with one of its sessions, in one query.

        Args:
            admin_id: The admin account the session must belong to.
            session_id: The session id (the access token's ``sid``).

        Returns:
            The (admin, session) pair, or None if either is missing or the
            session belongs to another admin.
        """
        try:
            stmt = (
                select(AdminAccount, AuthSession)
                .join(AuthSession, AuthSession.admin_account_id == AdminAccount.id)
                .where(AdminAccount.id == admin_id, AuthSession.id == session_id)
            )
            result = await self.session.execute(stmt)
            row = result.tuples().one_or_none()
            if row is None:
                return None
            return row[0], row[1]
        except Exception as e:
            raise RepositoryError(
                "Failed to get AuthSession with admin",
                operation="get_with_admin",
                original=e,
            ) from e

    async def delete_stale(self, now: datetime, *, revoked_before: datetime) -> int:
        """Delete sessions that can no longer be used or audited.

        A session goes when its absolute expiry has passed, when it was
        revoked before ``revoked_before``, or when it is not revoked but has
        no live refresh token left that has not expired. Its refresh tokens
        go with it; they are deleted explicitly as well, since SQLite only
        cascades with ``PRAGMA foreign_keys=ON``.

        A concurrent rotation can give a stale-looking session a new live
        token, so the candidates are locked first (``FOR UPDATE``, after any
        rotation holding them commits) and checked again by the DELETE, a new
        statement and so, under PostgreSQL's Read Committed, a new snapshot.
        A single DELETE would re-check only the session row after waiting,
        not its tokens. Sessions are locked before tokens are touched, the
        order rotation uses. On SQLite ``FOR UPDATE`` is not rendered: the
        candidate SELECT opens no transaction, and the DELETE takes the
        database write lock before it reads, so it sees committed rotations.

        Args:
            now: Current UTC datetime.
            revoked_before: Revoked sessions older than this are deleted.

        Returns:
            Number of sessions deleted.
        """
        try:
            has_live_token = (
                select(RefreshToken.id)
                .where(
                    RefreshToken.session_id == AuthSession.id,
                    RefreshToken.consumed_at.is_(None),
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
                .exists()
            )
            stale = or_(
                AuthSession.absolute_expires_at < now,
                AuthSession.revoked_at < revoked_before,
                and_(AuthSession.revoked_at.is_(None), ~has_live_token),
            )
            candidates = list(
                (
                    await self.session.scalars(
                        select(AuthSession.id)
                        .where(stale)
                        .order_by(AuthSession.id)
                        .with_for_update()
                    )
                ).all()
            )
            deleted = 0
            if candidates:
                sessions_stmt = (
                    delete(AuthSession)
                    .where(AuthSession.id.in_(candidates), stale)
                    .execution_options(synchronize_session=False)
                )
                result = await self.session.execute(sessions_stmt)
                deleted = _rowcount(result)
            orphans_stmt = (
                delete(RefreshToken)
                .where(
                    ~select(AuthSession.id)
                    .where(AuthSession.id == RefreshToken.session_id)
                    .exists()
                )
                .execution_options(synchronize_session=False)
            )
            _ = await self.session.execute(orphans_stmt)
            return deleted
        except Exception as e:
            raise RepositoryError(
                "Failed to delete stale auth sessions",
                operation="delete_stale",
                original=e,
            ) from e


class RefreshTokenRepository(Repository[RefreshToken]):
    """Repository for RefreshToken rows."""

    @property
    @override
    def _model_class(self) -> type[RefreshToken]:
        return RefreshToken

    async def get_by_token_hash(
        self, token_hash: str, *, current: bool = False
    ) -> RefreshToken | None:
        """Find a refresh token by its hash.

        Args:
            token_hash: The SHA-256 hash of the token.
            current: Re-read the row and replace any cached copy (use after
                taking the session lock).

        Returns:
            The RefreshToken if found, None otherwise.
        """
        try:
            stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            if current:
                stmt = stmt.execution_options(populate_existing=True)
            result = await self.session.execute(stmt)
            return result.unique().scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get RefreshToken by hash",
                operation="get_by_token_hash",
                original=e,
            ) from e

    async def count_live(self, session_id: UUID, generation: int) -> int:
        """Count a session's live tokens (not consumed, not revoked) at a generation.

        Args:
            session_id: The session.
            generation: The generation to count.

        Returns:
            The number of live tokens.
        """
        try:
            stmt = (
                select(func.count())
                .select_from(RefreshToken)
                .where(
                    RefreshToken.session_id == session_id,
                    RefreshToken.generation == generation,
                    RefreshToken.consumed_at.is_(None),
                    RefreshToken.revoked_at.is_(None),
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            raise RepositoryError(
                "Failed to count live refresh tokens",
                operation="count_live",
                original=e,
            ) from e

    async def revoke_live_siblings(
        self, session_id: UUID, generation: int, *, keep: UUID, now: datetime
    ) -> int:
        """Revoke a generation's live tokens other than ``keep``.

        Args:
            session_id: The session.
            generation: The generation whose tokens to revoke.
            keep: The token that is being consumed instead.
            now: Current UTC datetime.

        Returns:
            Number of tokens revoked.
        """
        try:
            stmt = (
                update(RefreshToken)
                .where(
                    RefreshToken.session_id == session_id,
                    RefreshToken.generation == generation,
                    RefreshToken.id != keep,
                    RefreshToken.consumed_at.is_(None),
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
                .execution_options(synchronize_session=False)
            )
            result = await self.session.execute(stmt)
            return _rowcount(result)
        except Exception as e:
            raise RepositoryError(
                "Failed to revoke sibling refresh tokens",
                operation="revoke_live_siblings",
                original=e,
            ) from e
