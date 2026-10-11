"""Base model and mixins for SQLAlchemy 2.0 async models.

Provides:
- Base: DeclarativeBase for all models; every ``Mapped[datetime]`` is a UTCDateTime
- UTCDateTime: a naive UTC column that reads and writes aware UTC datetimes
- UTCNow: a server-side "now" in UTC on SQLite and PostgreSQL alike
- TimestampMixin: created_at and updated_at timestamps
- UUIDPrimaryKeyMixin: UUID primary key generation

Timestamp contract: the database holds UTC wall-clock time in a column without a
time zone (SQLite ``DATETIME``, PostgreSQL ``timestamp without time zone``), and
Python only ever sees aware UTC datetimes. The conversion happens once, in
UTCDateTime, so callers write ``datetime.now(UTC)`` and compare what they read
with it directly.

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import ClassVar, final, override
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import TypeDecorator, TypeEngine


@final
class UTCDateTime(TypeDecorator[datetime]):
    """A ``DateTime`` column (no time zone) holding UTC, aware on the Python side.

    An aware value is converted to UTC and stored without its offset, which
    PostgreSQL's asyncpg driver requires for a ``timestamp without time zone``
    and which SQLite would otherwise drop silently. A naive value (one without
    a UTC offset) is taken to be UTC already, which is how the existing rows
    were written. Values read back carry ``tzinfo=UTC``.
    """

    impl = DateTime
    cache_ok: bool | None = True

    @override
    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            return value.replace(tzinfo=None)
        return value.astimezone(UTC).replace(tzinfo=None)

    @override
    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


@final
class UTCNow(FunctionElement[datetime]):
    """The current time in UTC, for server defaults of UTCDateTime columns.

    PostgreSQL's ``now()`` is a ``timestamptz``; assigned to a column without a
    time zone it becomes the session ``TimeZone``'s wall clock, so it is
    converted to UTC first. SQLite's ``CURRENT_TIMESTAMP`` is already UTC.
    """

    type: TypeEngine[datetime] = UTCDateTime()
    inherit_cache: bool | None = True
    name: str = "utcnow"


@compiles(UTCNow)
def compile_utcnow(_element: UTCNow, _compiler: SQLCompiler, **_kw: object) -> str:
    """SQLite and the default dialect: CURRENT_TIMESTAMP is UTC."""
    return "CURRENT_TIMESTAMP"


@compiles(UTCNow, "postgresql")
def compile_utcnow_postgresql(
    _element: UTCNow, _compiler: SQLCompiler, **_kw: object
) -> str:
    """PostgreSQL: now() converted to UTC wall-clock time."""
    return "(now() AT TIME ZONE 'utc')"


class Base(DeclarativeBase):
    """Base model for all SQLAlchemy models.

    All models should inherit from this class to share the same metadata
    and registry. ``Mapped[datetime]`` columns are UTCDateTime.
    """

    type_annotation_map: ClassVar[Mapping[type[datetime], TypeEngine[datetime]]] = {
        datetime: UTCDateTime()
    }


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps.

    The created_at field is set automatically on insert (by Python, or by the
    database when a statement omits it). The updated_at field is set
    automatically on update.
    """

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=UTCNow(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
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
