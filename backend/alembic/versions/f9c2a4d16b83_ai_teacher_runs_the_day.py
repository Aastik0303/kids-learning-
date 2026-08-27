"""The AI Teacher runs the day: a sitting belongs to a date and can end it.

The AI Teacher stopped being a sandbox: it is the class now, it runs today's
frozen plan one stage per planned item, and finishing the last stage locks the
day until tomorrow. Three columns carry that.

* `plan_date` - which day the sitting belongs to. A sitting left open overnight
  is yesterday's and is closed rather than carried on.
* `topic_correct` / `topic_answered` - this stage's own tally. The score handed
  to `learning_service.award_topic_completion` is computed from these in plain
  Python, which is what marks the level done and unlocks the next one on the
  Adventure map.

Existing rows are backfilled to the day they started on, which is the only
honest answer available for a sitting written before the column existed.

Revision ID: f9c2a4d16b83
Revises: e7d4b2c81a35
"""

from alembic import op
import sqlalchemy as sa


revision: str = "f9c2a4d16b83"
down_revision: str | None = "e7d4b2c81a35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("playground_sessions") as batch:
        batch.add_column(sa.Column("plan_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("topic_correct", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("topic_answered", sa.Integer(), nullable=False, server_default="0")
        )

    # A sitting written before this migration belongs to the day it opened on.
    # The two backends spell "the date part of a timestamp" differently, and
    # SQLite's CAST(... AS DATE) would quietly hand back a year, so each is
    # asked in its own words rather than in one that only looks portable.
    dialect = op.get_bind().dialect.name
    as_date = "date(started_at)" if dialect == "sqlite" else "CAST(started_at AS DATE)"
    op.execute(f"UPDATE playground_sessions SET plan_date = {as_date} WHERE plan_date IS NULL")

    with op.batch_alter_table("playground_sessions") as batch:
        batch.alter_column("plan_date", existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("playground_sessions") as batch:
        batch.drop_column("topic_answered")
        batch.drop_column("topic_correct")
        batch.drop_column("plan_date")
