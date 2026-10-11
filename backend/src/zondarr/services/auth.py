"""Authentication service for admin account management.

Orchestrates admin account creation, credential verification,
external auth (via provider registry), and the auth session lifecycle:
one session per sign-in, rotating refresh tokens within it.
"""

import asyncio
import hashlib
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import msgspec
import structlog

from zondarr.core.exceptions import AuthenticationError
from zondarr.media.registry import registry
from zondarr.models.admin import AdminAccount, AuthSession, RefreshToken
from zondarr.repositories.admin import (
    AdminAccountRepository,
    AuthSessionRepository,
    RefreshTokenRepository,
)
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.onboarding import OnboardingService, OnboardingStep
from zondarr.services.password import hash_password, needs_rehash, verify_password

if TYPE_CHECKING:
    from zondarr.config import Settings
    from zondarr.media.provider import AdminAuthDescriptor

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Refresh token defaults: each token expires after this much inactivity...
REFRESH_TOKEN_EXPIRY_DAYS = 7
REFRESH_TOKEN_BYTES = 32
# ...and no session outlives this, however often it refreshes.
SESSION_ABSOLUTE_DAYS = 14
# Live refresh tokens one session may hold (a successor plus the siblings
# issued when answers to the rotation were lost).
MAX_LIVE_TOKENS_PER_SESSION = 3
# Revoked sessions are kept this long for audit before cleanup deletes them.
REVOKED_SESSION_RETENTION_DAYS = 7

# Serializes concurrent setup attempts within a single process
_setup_lock = asyncio.Lock()


def _hash_token(token: str) -> str:
    """SHA-256 hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class Rotation(msgspec.Struct, frozen=True, kw_only=True):
    """Result of a successful refresh.

    Attributes:
        admin: The session's admin account (the caller checks ``enabled``).
        session_id: The session id, for the new access token's ``sid``.
        raw_token: The new raw refresh token (only returned once).
    """

    admin: AdminAccount
    session_id: UUID
    raw_token: str


class AuthService:
    """Service for authentication operations.

    Attributes:
        admin_repo: Repository for admin accounts.
        session_repo: Repository for auth sessions.
        token_repo: Repository for refresh tokens.
        app_setting_repo: Repository for app-level key/value settings.
    """

    admin_repo: AdminAccountRepository
    session_repo: AuthSessionRepository
    token_repo: RefreshTokenRepository
    app_setting_repo: AppSettingRepository
    onboarding_service: OnboardingService

    def __init__(
        self,
        admin_repo: AdminAccountRepository,
        session_repo: AuthSessionRepository,
        token_repo: RefreshTokenRepository,
        app_setting_repo: AppSettingRepository,
    ) -> None:
        self.admin_repo = admin_repo
        self.session_repo = session_repo
        self.token_repo = token_repo
        self.app_setting_repo = app_setting_repo
        self.onboarding_service = OnboardingService(admin_repo, app_setting_repo)

    async def setup_required(self) -> bool:
        """Check if initial admin setup is needed.

        Returns:
            True if no admin accounts exist.
        """
        count = await self.admin_repo.count()
        return count == 0

    async def get_onboarding_status(self) -> tuple[bool, OnboardingStep]:
        """Get onboarding requirement and current step."""
        return await self.onboarding_service.get_status()

    async def get_setup_and_onboarding_status(
        self,
    ) -> tuple[bool, bool, OnboardingStep]:
        """Get setup and onboarding status in one call.

        Returns:
            A tuple of (setup_required, onboarding_required, onboarding_step).
        """
        onboarding_required, onboarding_step = await self.get_onboarding_status()
        return onboarding_step == "account", onboarding_required, onboarding_step

    async def initialize_onboarding(self) -> None:
        """Initialize onboarding state right after first admin setup."""
        await self.onboarding_service.initialize_after_admin_setup()

    async def advance_onboarding(self) -> tuple[bool, OnboardingStep]:
        """Advance onboarding by one skip step and return updated status."""
        onboarding_step = await self.onboarding_service.advance_skip_step()
        return onboarding_step != "complete", onboarding_step

    async def create_admin(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
    ) -> AdminAccount:
        """Create a new local admin account.

        Args:
            username: Admin username.
            password: Plaintext password (will be hashed).
            email: Optional email address.

        Returns:
            The created AdminAccount.

        Raises:
            AuthenticationError: If username is already taken.
        """
        existing = await self.admin_repo.get_by_username(username)
        if existing is not None:
            raise AuthenticationError("Username already taken", "USERNAME_TAKEN")

        admin = AdminAccount(
            username=username,
            password_hash=hash_password(password),
            email=email,
            auth_method="local",
            enabled=True,
        )
        return await self.admin_repo.create(admin)

    async def setup_admin(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
    ) -> AdminAccount:
        """Atomically create the first admin account.

        Defence layers:
        1. asyncio.Lock serializes attempts within a single worker process
           (avoids wasted Argon2 hashing).
        2. INSERT ... WHERE NOT EXISTS prevents the insert when an admin
           already exists (single-statement check-and-insert).
        3. UNIQUE(username) + IntegrityError handling in the repository
           catches PostgreSQL races under READ COMMITTED isolation across
           multiple workers.

        Args:
            username: Admin username.
            password: Plaintext password (will be hashed).
            email: Optional email address.

        Returns:
            The created AdminAccount.

        Raises:
            AuthenticationError: If an admin already exists.
        """
        async with _setup_lock:
            pw_hash = hash_password(password)
            admin = await self.admin_repo.create_first_admin(
                username=username,
                password_hash=pw_hash,
                email=email,
                auth_method="local",
            )
            if admin is None:
                raise AuthenticationError(
                    "Setup already completed", "SETUP_NOT_REQUIRED"
                )
            logger.info(
                "admin_setup_completed",
                admin_id=str(admin.id),
                username=admin.username,
            )
            return admin

    async def authenticate_local(self, username: str, password: str) -> AdminAccount:
        """Authenticate with username and password.

        Args:
            username: Admin username.
            password: Plaintext password.

        Returns:
            The authenticated AdminAccount.

        Raises:
            AuthenticationError: If credentials are invalid or account is disabled.
        """
        admin = await self.admin_repo.get_by_username(username)
        if admin is None or admin.password_hash is None:
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        if not admin.enabled:
            raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")

        if not verify_password(admin.password_hash, password):
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        # Rehash if needed (updated Argon2 parameters)
        if needs_rehash(admin.password_hash):
            admin.password_hash = hash_password(password)

        admin.last_login_at = datetime.now(UTC)
        return admin

    async def authenticate_external(
        self,
        method: str,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
    ) -> AdminAccount:
        """Authenticate via an external provider.

        Delegates to the registered AdminAuthProvider for the given method.

        Args:
            method: The auth method name (e.g., "plex", "jellyfin").
            credentials: Provider-specific credential dict.
            settings: Application settings.

        Returns:
            The authenticated or auto-created AdminAccount.

        Raises:
            AuthenticationError: If the method is unknown or authentication fails.
        """
        # Defense-in-depth: block external auth during initial setup
        if await self.setup_required():
            raise AuthenticationError(
                "Initial setup must be completed first",
                "SETUP_REQUIRED",
            )

        provider = registry.get_admin_auth_provider(method)
        if provider is None:
            raise AuthenticationError(
                f"Unknown authentication method: {method}",
                "UNKNOWN_AUTH_METHOD",
            )

        if not provider.is_configured(settings):
            raise AuthenticationError(
                f"Authentication method not configured: {method}",
                "AUTH_METHOD_NOT_CONFIGURED",
            )

        return await provider.authenticate(
            credentials,
            settings=settings,
            admin_repo=self.admin_repo,
        )

    async def link_external_provider(
        self,
        admin_id: UUID,
        method: str,
        credentials: Mapping[str, str],
        *,
        settings: Settings,
    ) -> AdminAccount:
        """Link an external auth provider to an existing admin account.

        Verifies credentials via the provider's verify() method without
        creating any accounts, then updates the admin's external link.

        Args:
            admin_id: The admin account UUID to link.
            method: The auth method name (e.g., "plex", "jellyfin").
            credentials: Provider-specific credential dict.
            settings: Application settings.

        Returns:
            The updated AdminAccount with external link set.

        Raises:
            AuthenticationError: If the method is unknown, not configured,
                verification fails, or external_id is already taken.
        """
        provider = registry.get_admin_auth_provider(method)
        if provider is None:
            raise AuthenticationError(
                f"Unknown authentication method: {method}",
                "UNKNOWN_AUTH_METHOD",
            )

        if not provider.is_configured(settings):
            raise AuthenticationError(
                f"Authentication method not configured: {method}",
                "AUTH_METHOD_NOT_CONFIGURED",
            )

        # Verify credentials (does NOT create accounts)
        external_id, _display_name, email = await provider.verify(
            credentials, settings=settings
        )

        # Check no other admin already has this external ID
        existing = await self.admin_repo.get_by_external_id(external_id, method)
        if existing is not None:
            raise AuthenticationError(
                "External account already linked to another admin",
                "EXTERNAL_ID_TAKEN",
            )

        # Update admin's external link
        admin = await self.admin_repo.get_by_id(admin_id)
        if admin is None:
            raise AuthenticationError("Account not found", "ACCOUNT_NOT_FOUND")

        admin.auth_method = method
        admin.external_id = external_id
        if email and not admin.email:
            admin.email = email

        logger.info(
            "admin_external_provider_linked",
            admin_id=str(admin_id),
            method=method,
            external_id=external_id,
        )
        return admin

    async def start_session(
        self,
        admin: AdminAccount,
        *,
        user_agent: str | None,
        ip: str | None,
    ) -> tuple[UUID, str]:
        """Start a new auth session for a successful sign-in.

        Every sign-in (local, external, setup, TOTP completion) gets its own
        session, so replay detection and logout never touch the admin's
        other sessions.

        Args:
            admin: The signed-in admin account.
            user_agent: Client user-agent, for audit.
            ip: Client IP address, for audit.

        Returns:
            The session id (the access token's ``sid``) and the raw first
            refresh token (only returned once).
        """
        now = datetime.now(UTC)
        auth_session = AuthSession(
            id=uuid4(),
            admin_account_id=admin.id,
            absolute_expires_at=now + timedelta(days=SESSION_ABSOLUTE_DAYS),
            current_generation=0,
            user_agent=user_agent[:512] if user_agent else None,
            ip_address=ip[:45] if ip else None,
        )
        _ = await self.session_repo.create(auth_session)
        raw_token = await self._issue_token(auth_session, generation=0, now=now)
        return auth_session.id, raw_token

    async def rotate(self, raw_token: str) -> Rotation:
        """Exchange a refresh token for its successor, in one transaction.

        The session row is locked first (``AuthSessionRepository.lock``), so
        every rotation and revocation of a session runs serially on SQLite
        and PostgreSQL, and the token and session are re-read under the lock.

        - A live token of the current generation is consumed; its live
          siblings are revoked and a child of the next generation is issued.
        - A token consumed by the latest rotation whose successors are still
          unused (the answer to that rotation was lost) gets one more sibling
          of the current generation, up to MAX_LIVE_TOKENS_PER_SESSION live
          tokens.
        - An expired token ends the session (TOKEN_EXPIRED).
        - Anything else (a revoked token, an older generation, a token whose
          sibling was used, the sibling cap) is a replay and revokes this
          session only (TOKEN_REVOKED).

        Args:
            raw_token: The raw refresh token string.

        Returns:
            The rotation: admin, session id and the new raw refresh token. The
            caller still checks that the admin is enabled.

        Raises:
            AuthenticationError: INVALID_TOKEN, TOKEN_EXPIRED or TOKEN_REVOKED.
        """
        token_hash = _hash_token(raw_token)
        found = await self.token_repo.get_by_token_hash(token_hash)
        if found is None:
            raise AuthenticationError("Invalid refresh token", "INVALID_TOKEN")
        # Only the immutable session id of this unlocked read is trusted.
        session_id = found.session_id

        now = datetime.now(UTC)
        if not await self.session_repo.lock(session_id, now):
            raise AuthenticationError("Invalid refresh token", "INVALID_TOKEN")

        auth_session = await self.session_repo.get_current(session_id)
        token = await self.token_repo.get_by_token_hash(token_hash, current=True)
        if auth_session is None or token is None:
            raise AuthenticationError("Invalid refresh token", "INVALID_TOKEN")

        if (
            auth_session.revoked_at is not None
            or auth_session.absolute_expires_at <= now
        ):
            # Nothing to revoke: the session is over. The lock's write is
            # rolled back with the request.
            raise AuthenticationError("Token has been revoked", "TOKEN_REVOKED")

        generation = auth_session.current_generation
        live = token.consumed_at is None and token.revoked_at is None

        if live and token.generation == generation:
            if token.expires_at <= now:
                await self._end_after_failure(auth_session, reason="expired", now=now)
                raise AuthenticationError("Token has expired", "TOKEN_EXPIRED")
            token.consumed_at = now
            _ = await self.token_repo.revoke_live_siblings(
                session_id, generation, keep=token.id, now=now
            )
            auth_session.current_generation = generation + 1
            new_token = await self._issue_token(
                auth_session, generation=generation + 1, now=now
            )
            return await self._rotation(auth_session, new_token)

        if (
            token.consumed_at is not None
            and token.revoked_at is None
            and token.generation == generation - 1
        ):
            if token.consumed_at + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS) <= now:
                # Its successor would have expired by now as well.
                await self._end_after_failure(auth_session, reason="expired", now=now)
                raise AuthenticationError("Token has expired", "TOKEN_EXPIRED")
            live_count = await self.token_repo.count_live(session_id, generation)
            if live_count < MAX_LIVE_TOKENS_PER_SESSION:
                new_token = await self._issue_token(
                    auth_session, generation=generation, now=now
                )
                logger.info(
                    "refresh_token_recovered",
                    session_id=str(session_id),
                    admin_id=str(auth_session.admin_account_id),
                    generation=generation,
                    live_tokens=live_count + 1,
                )
                return await self._rotation(auth_session, new_token)

        logger.warning(
            "refresh_token_replay_detected",
            session_id=str(session_id),
            admin_id=str(auth_session.admin_account_id),
            token_generation=token.generation,
            session_generation=generation,
        )
        await self._end_after_failure(auth_session, reason="replay", now=now)
        raise AuthenticationError("Token has been revoked", "TOKEN_REVOKED")

    async def end_session(
        self,
        *,
        raw_refresh: str | None = None,
        session_id: UUID | None = None,
        reason: str,
    ) -> bool:
        """Revoke one session, found by its refresh token or by its id.

        The refresh token wins when it names a session; ``session_id`` (the
        access token's ``sid``) is used otherwise. Revoking a session twice
        changes nothing. The caller's transaction commits the revocation.

        Args:
            raw_refresh: A raw refresh token of the session, if known.
            session_id: The session id, if known.
            reason: Why (logout, replay, expired, admin).

        Returns:
            True if a session was revoked by this call.
        """
        target = None
        if raw_refresh:
            token = await self.token_repo.get_by_token_hash(_hash_token(raw_refresh))
            if token is not None:
                target = token.session_id
        if target is None:
            target = session_id
        if target is None:
            return False
        revoked = await self.session_repo.revoke(
            target, reason=reason, now=datetime.now(UTC)
        )
        if revoked:
            logger.info("auth_session_ended", session_id=str(target), reason=reason)
        return revoked

    async def _issue_token(
        self, auth_session: AuthSession, *, generation: int, now: datetime
    ) -> str:
        """Insert a refresh token of ``auth_session`` and return its raw value."""
        raw_token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
        refresh_token = RefreshToken(
            admin_account_id=auth_session.admin_account_id,
            session_id=auth_session.id,
            generation=generation,
            token_hash=_hash_token(raw_token),
            expires_at=min(
                now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
                auth_session.absolute_expires_at,
            ),
        )
        _ = await self.token_repo.create(refresh_token)
        return raw_token

    async def _rotation(self, auth_session: AuthSession, raw_token: str) -> Rotation:
        admin = await self.admin_repo.get_by_id(auth_session.admin_account_id)
        if admin is None:
            raise AuthenticationError("Invalid refresh token", "INVALID_TOKEN")
        return Rotation(admin=admin, session_id=auth_session.id, raw_token=raw_token)

    async def _end_after_failure(
        self, auth_session: AuthSession, *, reason: str, now: datetime
    ) -> None:
        """Revoke the session and commit, ahead of the error the caller raises.

        ``provide_db_session`` rolls back on an exception, so the revocation
        has to be committed before raising.
        """
        _ = await self.session_repo.revoke(auth_session.id, reason=reason, now=now)
        await self.session_repo.session.commit()

    async def update_email(self, admin_id: UUID, email: str | None) -> AdminAccount:
        """Update the email address on an admin account.

        Args:
            admin_id: The admin account UUID.
            email: New email, or None to clear.

        Returns:
            The updated AdminAccount.

        Raises:
            AuthenticationError: If the account is not found.
        """
        admin = await self.admin_repo.get_by_id(admin_id)
        if admin is None:
            raise AuthenticationError("Account not found", "ACCOUNT_NOT_FOUND")
        admin.email = email
        return admin

    async def change_password(
        self,
        admin_id: UUID,
        current_password: str,
        new_password: str,
    ) -> AdminAccount:
        """Change an admin's password after verifying the current one.

        Args:
            admin_id: The admin account UUID.
            current_password: Current password for verification.
            new_password: New password to set.

        Returns:
            The updated AdminAccount.

        Raises:
            AuthenticationError: If account not found, not local auth, or wrong password.
        """
        admin = await self.admin_repo.get_by_id(admin_id)
        if admin is None:
            raise AuthenticationError("Account not found", "ACCOUNT_NOT_FOUND")

        if admin.auth_method != "local":
            raise AuthenticationError(
                "Password change is only available for local accounts",
                "EXTERNAL_AUTH_NO_PASSWORD",
            )

        if admin.password_hash is None or not verify_password(
            admin.password_hash, current_password
        ):
            raise AuthenticationError(
                "Current password is incorrect", "INVALID_CREDENTIALS"
            )

        admin.password_hash = hash_password(new_password)
        logger.info("admin_password_changed", admin_id=str(admin_id))
        return admin

    async def get_available_auth_methods(
        self,
        *,
        settings: Settings,
    ) -> list[str]:
        """Get available authentication methods.

        Always includes 'local'. Adds external methods for each configured
        provider that supports admin auth.

        Args:
            settings: Application settings for checking provider configuration.

        Returns:
            List of available auth method strings.
        """
        methods: list[str] = ["local"]

        for desc in registry.get_admin_auth_descriptors():
            provider = registry.get_admin_auth_provider(desc.method_name)
            if provider is not None and provider.is_configured(settings):
                methods.append(desc.method_name)

        return methods

    async def get_auth_methods_with_providers(
        self,
        *,
        settings: Settings,
    ) -> tuple[list[str], list[AdminAuthDescriptor]]:
        """Get available auth methods and their provider descriptors.

        Combines method availability checking with descriptor filtering
        so the controller doesn't need to re-query the registry.

        Args:
            settings: Application settings for checking provider configuration.

        Returns:
            A tuple of (method names, filtered admin auth descriptors).
        """
        methods = await self.get_available_auth_methods(settings=settings)
        descriptors = [
            desc
            for desc in registry.get_admin_auth_descriptors()
            if desc.method_name in methods
        ]
        return methods, descriptors
