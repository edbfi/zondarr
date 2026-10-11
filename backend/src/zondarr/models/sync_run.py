"""SyncRun model for tracking media server synchronization executions.

Stores per-run metadata for both library and user sync operations so the API
can expose last successful sync times and troubleshooting context.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SyncRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A recorded synchronization run for a media server.

    Attributes:
        id: UUID primary key.
        media_server_id: FK to the related media server.
        sync_type: Sync channel ("libraries" or "users").
        trigger: Run trigger source ("automatic", "manual", or "onboarding").
        status: Run outcome ("success" or "failed").
        started_at: Timestamp when execution started.
        finished_at: Timestamp when execution finished.
        error_message: Optional failure reason for troubleshooting.
        created_at: Record creation time.
        updated_at: Last record update time.
    """

    __tablename__: str = "sync_runs"

    media_server_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_servers.id", ondelete="CASCADE")
    )
    sync_type: Mapped[str] = mapped_column(String(32))
    trigger: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__: tuple[
        Index, Index, CheckConstraint, CheckConstraint, CheckConstraint
    ] = (
        Index("ix_sync_runs_media_server_id", "media_server_id"),
        Index(
            "ix_sync_runs_server_type_started",
            "media_server_id",
            "sync_type",
            "started_at",
        ),
        CheckConstraint(
            "sync_type IN ('libraries', 'users')",
            name="ck_sync_runs_sync_type",
        ),
        CheckConstraint(
            "trigger IN ('automatic', 'manual', 'onboarding')",
            name="ck_sync_runs_trigger",
        ),
        CheckConstraint(
            "status IN ('success', 'failed')",
            name="ck_sync_runs_status",
        ),
    )
