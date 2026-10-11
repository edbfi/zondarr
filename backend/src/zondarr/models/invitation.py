"""Invitation model and association tables for invitation management.

Provides:
- Invitation: Model representing a secure invitation code for media server access
- invitation_servers: Association table linking invitations to target media servers
- invitation_libraries: Association table linking invitations to allowed libraries

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
Association tables use Table construct for many-to-many relationships.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from zondarr.models.media_server import Library, MediaServer

if TYPE_CHECKING:
    from zondarr.models.wizard import Wizard

# Association table for invitation-to-media-server many-to-many relationship
invitation_servers: Table = Table(
    "invitation_servers",
    Base.metadata,
    Column[UUID]("invitation_id", ForeignKey("invitations.id"), primary_key=True),
    Column[UUID]("media_server_id", ForeignKey("media_servers.id"), primary_key=True),
)

# Association table for invitation-to-library many-to-many relationship
invitation_libraries: Table = Table(
    "invitation_libraries",
    Base.metadata,
    Column[UUID]("invitation_id", ForeignKey("invitations.id"), primary_key=True),
    Column[UUID]("library_id", ForeignKey("libraries.id"), primary_key=True),
)


class Invitation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A secure invitation code for media server access.

    Represents a time-limited, usage-limited invitation that grants access
    to one or more media servers and optionally specific libraries.

    Attributes:
        id: UUID primary key
        code: Unique invitation code (e.g., "ABC123XYZ")
        expires_at: Optional expiration timestamp (None = never expires)
        max_uses: Optional maximum number of redemptions (None = unlimited)
        use_count: Current number of times the invitation has been redeemed
        duration_days: Optional duration in days for user access after redemption
        enabled: Whether the invitation is currently active
        created_by: Optional identifier of who created the invitation
        pre_wizard_id: Optional FK to wizard to run before account creation
        post_wizard_id: Optional FK to wizard to run after account creation
        created_at: Timestamp when the invitation was created
        updated_at: Timestamp of last modification
        target_servers: List of media servers this invitation grants access to
        allowed_libraries: List of specific libraries this invitation grants access to
        pre_wizard: Optional wizard to run before account creation
        post_wizard: Optional wizard to run after account creation
    """

    __tablename__: str = "invitations"
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            "max_uses IS NULL OR use_count <= max_uses",
            name="ck_invitations_use_count_le_max_uses",
        ),
    )

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    max_uses: Mapped[int | None] = mapped_column(Integer, default=None)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_days: Mapped[int | None] = mapped_column(Integer, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255), default=None)

    # Wizard foreign keys - SET NULL on wizard deletion
    pre_wizard_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wizards.id", ondelete="SET NULL"),
        default=None,
    )
    post_wizard_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wizards.id", ondelete="SET NULL"),
        default=None,
    )

    # Relationships - many-to-many via association tables
    target_servers: Mapped[list[MediaServer]] = relationship(
        secondary=invitation_servers,
        lazy="selectin",  # Eager load for async contexts
    )
    allowed_libraries: Mapped[list[Library]] = relationship(
        secondary=invitation_libraries,
        lazy="selectin",  # Eager load for async contexts
    )

    # Wizard relationships - use selectin for eager loading
    pre_wizard: Mapped[Wizard | None] = relationship(
        foreign_keys=[pre_wizard_id],
        lazy="selectin",
    )
    post_wizard: Mapped[Wizard | None] = relationship(
        foreign_keys=[post_wizard_id],
        lazy="selectin",
    )
