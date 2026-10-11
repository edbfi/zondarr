"""Identity and User models for user management.

Provides:
- Identity: Model representing a user's account within Zondarr
- User: Model representing a media server account linked to an Identity

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
Relationships use selectinload for collections and joined for single relations
to avoid N+1 query issues in async contexts.

An Identity can have multiple Users across different media servers,
enabling unified management of access across Plex and Jellyfin instances.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from zondarr.models.media_server import MediaServer

if TYPE_CHECKING:
    from zondarr.models.invitation import Invitation


class Identity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A user's account within Zondarr.

    Represents a person who has access to one or more media servers.
    An Identity links to multiple User accounts across different servers,
    enabling centralized management of media server access.

    Attributes:
        id: UUID primary key
        display_name: Human-readable name for the identity
        email: Optional email address for notifications
        expires_at: Optional expiration timestamp (None = never expires)
        enabled: Whether the identity is currently active
        created_at: Timestamp when the identity was created
        updated_at: Timestamp of last modification
        users: List of media server accounts linked to this identity
    """

    __tablename__: str = "identities"

    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships - use selectinload for collections to avoid N+1
    users: Mapped[list[User]] = relationship(
        back_populates="identity",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eager load by default
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A media server account linked to an Identity.

    Represents a user account on a specific media server (Plex or Jellyfin)
    that is managed by Zondarr. Each User belongs to exactly one Identity
    and one MediaServer.

    Attributes:
        id: UUID primary key
        identity_id: Foreign key to the parent identity
        media_server_id: Foreign key to the media server
        invitation_id: Optional foreign key to the invitation that created this user
        external_user_id: The user's ID on the media server
        username: The username on the media server
        expires_at: Optional expiration timestamp (None = never expires)
        enabled: Whether the user account is currently active
        created_at: Timestamp when the user was created
        updated_at: Timestamp of last modification
        identity: Reference to the parent identity
        media_server: Reference to the media server
        invitation: Optional reference to the source invitation
    """

    __tablename__: str = "users"

    identity_id: Mapped[UUID] = mapped_column(ForeignKey("identities.id"))
    media_server_id: Mapped[UUID] = mapped_column(ForeignKey("media_servers.id"))
    invitation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("invitations.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    external_user_id: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255))
    external_user_type: Mapped[str | None] = mapped_column(String(50), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Table-level indexes and constraints
    __table_args__: tuple[Index | UniqueConstraint, ...] = (
        Index("ix_users_media_server_id", "media_server_id"),
        Index("ix_users_identity_id", "identity_id"),
        Index("ix_users_enabled_expires", "enabled", "expires_at"),
        UniqueConstraint(
            "external_user_id",
            "media_server_id",
            name="uq_users_external_user_server",
        ),
        UniqueConstraint(
            "username",
            "media_server_id",
            name="uq_users_username_server",
        ),
    )

    # Relationships - use joined for single relations
    identity: Mapped[Identity] = relationship(
        back_populates="users",
        lazy="joined",
    )
    media_server: Mapped[MediaServer] = relationship(
        lazy="joined",
    )
    invitation: Mapped[Invitation | None] = relationship(
        lazy="joined",
    )
