"""utc timestamps on postgresql

Every timestamp column holds naive UTC (models/base.py, UTCDateTime). On
PostgreSQL that needs two changes; SQLite already stores it that way, so this
revision does nothing there and leaves SQLite data untouched.

- ``expires_at`` of identities, invitations and users was created as
  ``timestamptz``; it becomes ``timestamp`` holding the same instant in UTC.
  A column that is already ``timestamp`` is left as it is.
- ``created_at`` defaulted to ``CURRENT_TIMESTAMP``, which a ``timestamp``
  column stores as the session time zone's wall clock; it now defaults to
  ``now()`` in UTC.

Revision ID: 6ff80f942e51
Revises: 75f25ededea9
Create Date: 2026-10-12 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "6ff80f942e51"
down_revision: str | None = "75f25ededea9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The tables as of this revision, not the evolving models.
EXPIRES_AT_TABLES = ("identities", "invitations", "users")
CREATED_AT_TABLES = (
    "admin_accounts",
    "app_settings",
    "auth_sessions",
    "identities",
    "invitations",
    "libraries",
    "media_servers",
    "oauth_sessions",
    "refresh_tokens",
    "step_interactions",
    "sync_runs",
    "users",
    "wizard_step_translations",
    "wizard_steps",
    "wizards",
)
UTC_NOW = sa.text("(now() AT TIME ZONE 'utc')")
CURRENT_TIMESTAMP = sa.text("CURRENT_TIMESTAMP")


def _column_type(table: str, column: str) -> str:
    """The column's PostgreSQL type, for the table ALTER TABLE resolves.

    ``to_regclass`` follows ``search_path`` exactly as the unqualified
    ``ALTER TABLE`` does, wherever the table's schema is on it.
    """
    data_type = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute"
                " WHERE attrelid = to_regclass(CAST(:table AS text))"
                " AND attname = :column AND NOT attisdropped"
            ),
            {"table": table, "column": column},
        )
        .scalar_one()
    )
    return str(data_type)


def upgrade() -> None:
    """Store expires_at as naive UTC and default created_at to UTC (PostgreSQL)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in EXPIRES_AT_TABLES:
        if _column_type(table, "expires_at") == "timestamp with time zone":
            op.alter_column(
                table,
                "expires_at",
                type_=sa.DateTime(),
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=True,
                postgresql_using="expires_at AT TIME ZONE 'UTC'",
            )
    for table in CREATED_AT_TABLES:
        op.alter_column(
            table,
            "created_at",
            server_default=UTC_NOW,
            existing_type=sa.DateTime(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Restore the timestamptz expires_at columns and CURRENT_TIMESTAMP defaults."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in CREATED_AT_TABLES:
        op.alter_column(
            table,
            "created_at",
            server_default=CURRENT_TIMESTAMP,
            existing_type=sa.DateTime(),
            existing_nullable=False,
        )
    for table in EXPIRES_AT_TABLES:
        if _column_type(table, "expires_at") == "timestamp without time zone":
            op.alter_column(
                table,
                "expires_at",
                type_=sa.DateTime(timezone=True),
                existing_type=sa.DateTime(),
                existing_nullable=True,
                postgresql_using="expires_at AT TIME ZONE 'UTC'",
            )
