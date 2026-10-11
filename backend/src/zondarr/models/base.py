"""Base model and mixins for SQLAlchemy 2.0 async models.

Provides:
- Base: DeclarativeBase for all models
- TimestampMixin: created_at and updated_at timestamps with timezone-aware UTC
- UTCDateTime: a naive UTC column that reads and writes aware UTC datetimes
- UTCTimestampMixin: TimestampMixin's columns as UTCDateTime
- UUIDPrimaryKeyMixin: UUID primary key generation

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
"""

from datetime import UTC, datetime
from typing import final, override
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    """Base model for all SQLAlchemy models.

    All models should inherit from this class to share the same metadata
    and registry.
    """


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps.

    Uses timezone-aware UTC datetimes for consistency across deployments.
    The created_at field is set automatically on insert.
    The updated_at field is set automatically on update.
    """

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        default=None,
        onupdate=lambda: datetime.now(UTC),
    )


@final
class UTCDateTime(TypeDecorator[datetime]):
    """A ``DateTime`` column (no time zone) holding UTC, aware on the Python side.

    Values are stored as naive UTC, the same DDL as a plain ``DateTime``, so
    PostgreSQL's asyncpg driver accepts them (it rejects an aware value for a
    ``timestamp without time zone``). Values read back carry ``tzinfo=UTC``,
    so they compare with ``datetime.now(UTC)`` on SQLite and PostgreSQL alike.
    A naive value written to the column is taken to be UTC already.
    """

    impl = DateTime
    cache_ok: bool | None = True

    @override
    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @override
    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class UTCTimestampMixin:
    """TimestampMixin with ``UTCDateTime`` columns (same DDL, aware values)."""

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        default=None,
        onupdate=lambda: datetime.now(UTC),
    )


class UUIDPrimaryKeyMixin:
    """Mixin providing UUID primary key.

    Generates a new UUID4 for each entity on creation.
    """

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
