"""playground_sessions and playground_turns - the AI Teacher's own world

The AI Teacher is a sandbox: a retrieval-grounded agent that explains from
`data/playground/teacher_notes.md`, asks its own questions and keeps its own
points. Its two tables are prefixed and separate because nothing in it is a fact
about the child - no attempt, no star, no mastery, no plan - and keeping the
rows apart is what makes that checkable rather than promised.

Revision ID: c3a9e17b5d02
Revises: b7f1a2c9d4e3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import UTCDateTime


revision: str = "c3a9e17b5d02"
down_revision: str | None = "b7f1a2c9d4e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playground_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "child_id",
            sa.Uuid(),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("subject_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("topic_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("questions_asked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strategies_spent", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("pending_question", sa.Text(), nullable=False, server_default=""),
        sa.Column("pending_answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("pending_accept", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="in_progress"),
        sa.Column("started_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_playground_sessions_child", "playground_sessions", ["child_id", "started_at"]
    )

    op.create_table(
        "playground_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("strategy", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="template"),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("child_answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("points_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_playground_turns_session", "playground_turns", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_playground_turns_session", table_name="playground_turns")
    op.drop_table("playground_turns")
    op.drop_index("ix_playground_sessions_child", table_name="playground_sessions")
    op.drop_table("playground_sessions")
