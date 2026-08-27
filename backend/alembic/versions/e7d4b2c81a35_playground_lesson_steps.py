"""playground_sessions: lesson steps and the plan cursor

The AI Teacher now teaches one concept through a sequence - explain it, say it,
draw it, match it, one more question - and a stage is a topic out of today's
plan rather than a number that only counts up. Both live on the row, because the
client holding either would be the client deciding the lesson.

Revision ID: e7d4b2c81a35
Revises: d5c81f4a9b76
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e7d4b2c81a35"
down_revision: str | None = "d5c81f4a9b76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("playground_sessions", sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("playground_sessions", sa.Column("step_tries", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("playground_sessions", sa.Column("plan_topics", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("playground_sessions", sa.Column("plan_index", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("playground_sessions", "plan_index")
    op.drop_column("playground_sessions", "plan_topics")
    op.drop_column("playground_sessions", "step_tries")
    op.drop_column("playground_sessions", "step_index")
