"""add auth sessions

Every sign-in becomes an auth session that owns a family of rotating refresh
tokens. Live legacy refresh tokens become one session each (no forced
re-login); consumed, revoked and expired ones are deleted.

Revision ID: 75f25ededea9
Revises: a1b2c3d4e5f6
Create Date: 2026-10-11 12:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "75f25ededea9"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Absolute lifetime given to a session made from a legacy token, counted from
# the token's creation (its lineage before that was never recorded).
LEGACY_SESSION_DAYS = 14

SESSION_FK = "fk_refresh_tokens_session_id_auth_sessions"

auth_sessions = sa.table(
    "auth_sessions",
    sa.column("id", sa.Uuid()),
    sa.column("admin_account_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime()),
    sa.column("absolute_expires_at", sa.DateTime()),
    sa.column("revoked_at", sa.DateTime()),
    sa.column("current_generation", sa.Integer()),
    sa.column("user_agent", sa.String()),
    sa.column("ip_address", sa.String()),
)

refresh_tokens = sa.table(
    "refresh_tokens",
    sa.column("id", sa.Uuid()),
    sa.column("admin_account_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime()),
    sa.column("expires_at", sa.DateTime()),
    sa.column("revoked", sa.Boolean()),
    sa.column("user_agent", sa.String()),
    sa.column("ip_address", sa.String()),
    sa.column("session_id", sa.Uuid()),
    sa.column("generation", sa.Integer()),
    sa.column("consumed_at", sa.DateTime()),
    sa.column("revoked_at", sa.DateTime()),
)


def upgrade() -> None:
    """Create auth_sessions and attach refresh tokens to them."""
    op.create_table(
        "auth_sessions",
        sa.Column("admin_account_id", sa.Uuid(), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_refresh_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=32), nullable=True),
        sa.Column(
            "current_generation", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["admin_account_id"], ["admin_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_auth_sessions_admin_account_id"),
            ["admin_account_id"],
            unique=False,
        )

    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("generation", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("consumed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(), nullable=True))

    # Each live legacy token becomes its own session, with the token's id.
    bind = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    live = bind.execute(
        sa.select(
            refresh_tokens.c.id,
            refresh_tokens.c.admin_account_id,
            refresh_tokens.c.created_at,
            refresh_tokens.c.user_agent,
            refresh_tokens.c.ip_address,
        ).where(
            refresh_tokens.c.revoked == sa.false(),
            refresh_tokens.c.expires_at > now,
        )
    ).all()
    if live:
        _ = bind.execute(
            sa.insert(auth_sessions),
            [
                {
                    "id": row.id,
                    "admin_account_id": row.admin_account_id,
                    "created_at": row.created_at,
                    "absolute_expires_at": row.created_at
                    + timedelta(days=LEGACY_SESSION_DAYS),
                    "current_generation": 0,
                    "user_agent": row.user_agent,
                    "ip_address": row.ip_address,
                }
                for row in live
            ],
        )
        _ = bind.execute(
            sa.update(refresh_tokens)
            .where(refresh_tokens.c.id.in_(sa.select(auth_sessions.c.id)))
            .values(session_id=refresh_tokens.c.id, generation=0)
        )
    _ = bind.execute(
        sa.delete(refresh_tokens).where(refresh_tokens.c.session_id.is_(None))
    )

    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.alter_column("session_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.alter_column("generation", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            SESSION_FK, "auth_sessions", ["session_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_token_hash"))
        batch_op.create_index(
            batch_op.f("ix_refresh_tokens_token_hash"), ["token_hash"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_refresh_tokens_session_id"), ["session_id"], unique=False
        )
        batch_op.drop_column("revoked")
        batch_op.drop_column("user_agent")
        batch_op.drop_column("ip_address")


def downgrade() -> None:
    """Detach refresh tokens from sessions and drop auth_sessions.

    A token that is no longer live (consumed, revoked, or of a revoked
    session) comes back as ``revoked``; user agent and IP address come back
    from the token's session.
    """
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("revoked", sa.Boolean(), nullable=True))
        batch_op.add_column(
            sa.Column("user_agent", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ip_address", sa.String(length=45), nullable=True)
        )

    bind = op.get_bind()
    session_of_token = auth_sessions.c.id == refresh_tokens.c.session_id
    revoked_sessions = sa.select(auth_sessions.c.id).where(
        auth_sessions.c.revoked_at.is_not(None)
    )
    _ = bind.execute(
        sa.update(refresh_tokens).values(
            revoked=sa.or_(
                refresh_tokens.c.consumed_at.is_not(None),
                refresh_tokens.c.revoked_at.is_not(None),
                refresh_tokens.c.session_id.in_(revoked_sessions),
            ),
            user_agent=sa.select(auth_sessions.c.user_agent)
            .where(session_of_token)
            .scalar_subquery(),
            ip_address=sa.select(auth_sessions.c.ip_address)
            .where(session_of_token)
            .scalar_subquery(),
        )
    )

    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.alter_column("revoked", existing_type=sa.Boolean(), nullable=False)
        batch_op.drop_constraint(SESSION_FK, type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_session_id"))
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_token_hash"))
        batch_op.create_index(
            batch_op.f("ix_refresh_tokens_token_hash"), ["token_hash"], unique=False
        )
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("consumed_at")
        batch_op.drop_column("generation")
        batch_op.drop_column("session_id")

    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auth_sessions_admin_account_id"))

    op.drop_table("auth_sessions")
