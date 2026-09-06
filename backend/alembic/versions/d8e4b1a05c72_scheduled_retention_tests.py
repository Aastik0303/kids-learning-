"""Retention tests as part of the schedule.

A concept taught today becomes eligible for a deterministic retention test two
days later, the scheduler decides when it is asked, and its result pays the
**original teaching episode's** Q-value. This migration adds the three things
that chain needs and nothing else.

**`retention_tests`** is the chain itself: child, concept, the teaching episode
it was scheduled off, when it came due, what was asked, what came back, what it
paid and when it settled. The unique constraint on
`source_teaching_episode_id` is the idempotency of the whole feature - a sweep
that runs every fifteen minutes, two workers, or a retry all write one row per
episode, and an episode paid twice is not a rounding error: the Q-update moves
by `alpha * (target - Q)`, so counting one child's Tuesday twice counts two
children.

**`policy_episodes.question_ref`** records which authored question a teaching
turn taught around, so the test scheduled off it can ask a *different* one about
the same concept. Without it "do not simply repeat the exact same question" is
a hope rather than a rule, and the transfer bonus cannot be told from recall.
Empty on every row written before this, which is the truth about them: those
episodes are paid by the older opportunistic probe, and a test scheduled off one
of them asks the concept's first authored question and pays no transfer bonus.

**`playground_sessions.retention_queue` / `retention_index`** hold the check-ins
one sitting opened with, so a reload finds the same one in front of the child
rather than a new queue.

Nothing here touches a level, a star, an unlock or a certificate. The only thing
downstream of this table is a Q-value.

Revision ID: d8e4b1a05c72
Revises: a7c31d9e04b5
"""

from alembic import op
import sqlalchemy as sa


revision: str = "d8e4b1a05c72"
down_revision: str | None = "a7c31d9e04b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retention_tests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "child_id",
            sa.Uuid(),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # "<subject>:<topic>" - the same skill id the episode was written
        # against, so the test and the teaching it judges line up on one concept.
        sa.Column("concept_id", sa.String(length=64), nullable=False),
        sa.Column("topic_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "source_teaching_episode_id",
            sa.Uuid(),
            sa.ForeignKey("policy_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("question_ref", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("taught_question_ref", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("result", sa.String(length=8), nullable=True),
        sa.Column("reward", sa.Float(), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("episodes_paid", sa.Integer(), nullable=False, server_default="0"),
        # The idempotency of the scheduler, in one line.
        sa.UniqueConstraint(
            "source_teaching_episode_id", name="uq_retention_tests_source_episode"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'settled', 'void')", name="retention_status_values"
        ),
        sa.CheckConstraint(
            "result IS NULL OR result IN ('pass', 'fail')", name="retention_result_values"
        ),
    )
    # The scheduler's own query: this child's pending tests that have come due.
    op.create_index(
        "ix_retention_tests_due", "retention_tests", ["child_id", "status", "due_at"]
    )
    op.create_index(
        "ix_retention_tests_concept", "retention_tests", ["child_id", "concept_id", "due_at"]
    )

    op.add_column(
        "policy_episodes",
        sa.Column("question_ref", sa.String(length=64), nullable=False, server_default=""),
    )

    op.add_column(
        "playground_sessions",
        sa.Column("retention_queue", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "playground_sessions",
        sa.Column("retention_index", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("playground_sessions", "retention_index")
    op.drop_column("playground_sessions", "retention_queue")
    op.drop_column("policy_episodes", "question_ref")
    op.drop_index("ix_retention_tests_concept", table_name="retention_tests")
    op.drop_index("ix_retention_tests_due", table_name="retention_tests")
    op.drop_table("retention_tests")
