"""playground_sessions.pending_options - the choices the bot offered

The AI Teacher now offers two or three things to tap beside its question. They
are held on the row for the same reason the expected answer is: a reload has to
show the same question *and* the same choices, and the client is never the thing
that remembers either.

Revision ID: d5c81f4a9b76
Revises: c3a9e17b5d02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d5c81f4a9b76"
down_revision: str | None = "c3a9e17b5d02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playground_sessions",
        sa.Column("pending_options", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("playground_sessions", "pending_options")
