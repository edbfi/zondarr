"""Admin authentication models.

Provides:
- AdminAccount: Admin user account for Zondarr dashboard access
- AuthSession: One sign-in, owning a family of rotating refresh tokens
- RefreshToken: Rotating refresh tokens of an auth session (stored hashed)
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdminAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin user account for Zondarr dashboard access.

    Separate from Identity/User which represent media server accounts.
    Supports local password auth and external auth via registered providers.

    Attributes:
        id: UUID primary key.
        username: Unique admin username.
        password_hash: Argon2id hash (nullable for external auth).
        email: Optional email address.
        auth_method: How this admin authenticates.
        external_id: External service identifier for the auth provider.
        enabled: Whether this admin can log in.
        last_login_at: Timestamp of last successful login.
        totp_enabled: Whether TOTP two-factor authentication is active.
        totp_secret_encrypted: Fernet-encrypted TOTP secret (base32).
        totp_backup_codes: JSON array of argon2-hashed backup codes.
    """

    __tablename__: str = "admin_accounts"

    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    auth_method: Mapped[str] = mapped_column(String(50), default="local")
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)

    # TOTP two-factor authentication
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    totp_backup_codes: Mapped[str | None] = mapped_column(Text, default=None)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(default=None)
    totp_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    totp_last_failed_at: Mapped[datetime | None] = mapped_column(default=None)
    totp_challenge_nonce: Mapped[str | None] = mapped_column(String(64), default=None)
    totp_last_used_code: Mapped[str | None] = mapped_column(String(6), default=None)
    totp_last_used_at: Mapped[int | None] = mapped_column(Integer, default=None)

    # Relationships
    auth_sessions: Mapped[list[AuthSession]] = relationship(
        cascade="all, delete-orphan",
        lazy="noload",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="admin_account",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__: tuple[Index, ...] = (
        Index("ix_admin_accounts_external_id", "external_id"),
    )


class AuthSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One sign-in of an admin: the family of refresh tokens it issues.

    Created by every successful login (local, external, setup, TOTP
    completion) and never extended past ``absolute_expires_at``. Refresh
    rotation, replay detection and logout all act on one session, never on
    the admin's other sessions. Access tokens carry the session id (``sid``)
    and stop working once the session is revoked or expired.

    Invariant: every live refresh token of a session has
    ``generation == current_generation``.

    Attributes:
        id: UUID primary key (also the ``sid`` claim of its access tokens).
        admin_account_id: FK to the owning admin account.
        absolute_expires_at: Hard end of the session; refreshes never extend it.
        last_refresh_at: When a refresh last touched the session.
        revoked_at: When the session was revoked, if it was.
        revoked_reason: Why: logout, replay, expired or admin.
        current_generation: Generation of the session's live refresh tokens.
        user_agent: Client user-agent at sign-in, for audit.
        ip_address: Client IP address at sign-in, for audit.
    """

    __tablename__: str = "auth_sessions"

    admin_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        index=True,
    )
    absolute_expires_at: Mapped[datetime] = mapped_column()
    last_refresh_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_reason: Mapped[str | None] = mapped_column(String(32), default=None)
    current_generation: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Rotating refresh token of an auth session.

    Stored hashed (SHA-256); only the hash is persisted. A token is live while
    both ``consumed_at`` and ``revoked_at`` are unset.

    Attributes:
        id: UUID primary key.
        admin_account_id: FK to the owning admin account.
        session_id: FK to the auth session the token belongs to.
        generation: Rotation generation within the session.
        token_hash: SHA-256 hash of the refresh token value (unique).
        expires_at: Sliding inactivity expiry of this token.
        consumed_at: When a refresh exchanged this token for its successor.
        revoked_at: When the token was revoked without being exchanged.
    """

    __tablename__: str = "refresh_tokens"

    admin_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    generation: Mapped[int] = mapped_column(Integer)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column()
    consumed_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)

    # Relationships
    admin_account: Mapped[AdminAccount] = relationship(
        back_populates="refresh_tokens",
        lazy="joined",
    )
