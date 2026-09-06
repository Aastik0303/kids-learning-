"""An episode that can be audited, and a Q-table two workers can share.

Two problems, one migration.

**Attribution.** `policy_episodes` held the discretised state key and nothing
else about the turn. A reward paid seven days later landed on a row that could
not say which question was being taught, where the child's mastery stood, which
probe paid it or what the Q-value was on either side of the update. That is
enough to train a table and not enough to ever explain one. The columns added
here are the audit trail, and nothing downstream of a mark, a star or an unlock
reads any of them.

**Concurrency.** `policy_q_values` had its unique constraint from the start, so
duplicate `(state_key, action)` rows were never possible; what it did not have
was an index for the read that happens on every single teaching turn - all nine
actions of one state - on backends that will not use a unique index for a prefix
scan. The repository's insert now runs in a SAVEPOINT and resolves a conflict by
reading the row the other worker wrote, so the constraint is load-bearing rather
than merely decorative.

Revision ID: a7c31d9e04b5
Revises: b2e5c07d31af
"""

from alembic import op
import sqlalchemy as sa


revision: str = "a7c31d9e04b5"
down_revision: str | None = "b2e5c07d31af"
branch_labels = None
depends_on = None


# Every added column is nullable or has a server default, so the rows written
# before this migration stay readable: an old episode simply has no mastery
# reading and no probe verdict, which is the truth about it.
NEW_COLUMNS = (
    sa.Column("activity_id", sa.String(length=64), nullable=False, server_default=""),
    sa.Column("rung", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("spent_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("mastery_before", sa.Float(), nullable=True),
    sa.Column("mastery_after", sa.Float(), nullable=True),
    sa.Column("arm", sa.String(length=8), nullable=False, server_default="rl"),
    sa.Column("shadow_action", sa.String(length=20), nullable=True),
    sa.Column("explored", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("explore_rate", sa.Float(), nullable=False, server_default="0"),
    sa.Column("leak_kind", sa.String(length=16), nullable=False, server_default="none"),
    sa.Column("probe_kind", sa.String(length=8), nullable=True),
    sa.Column("probe_passed", sa.Boolean(), nullable=True),
    sa.Column("q_before", sa.Float(), nullable=True),
    sa.Column("q_after", sa.Float(), nullable=True),
)


def upgrade() -> None:
    with op.batch_alter_table("policy_episodes") as batch:
        for column in NEW_COLUMNS:
            batch.add_column(column)
    op.create_index("ix_policy_episodes_probe", "policy_episodes", ["retention_probe_id"])
    op.create_index(
        "ix_policy_episodes_child_skill", "policy_episodes", ["child_id", "skill_id", "taken_at"]
    )
    op.create_index("ix_policy_q_values_state", "policy_q_values", ["state_key"])


def downgrade() -> None:
    op.drop_index("ix_policy_q_values_state", table_name="policy_q_values")
    op.drop_index("ix_policy_episodes_child_skill", table_name="policy_episodes")
    op.drop_index("ix_policy_episodes_probe", table_name="policy_episodes")
    with op.batch_alter_table("policy_episodes") as batch:
        for column in reversed(NEW_COLUMNS):
            batch.drop_column(column.name)
