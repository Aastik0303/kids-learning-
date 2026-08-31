"""The day's plan owns its own cursor.

`plan_cursor` used to decide which item the child was on by asking whether the
topic was in their lifetime `completed_topics`. That is right for a level the
child has never finished and wrong for the one kind of item the planner freezes
*because* it is already finished: a `revisit`, which is a level marked weak and
played again. Such an item was born ticked. A day made of three of them had no
current topic, `is_day_complete` was true before the class opened, and the AI
Teacher wrote `day_complete` and locked the child out of a plan that had taught
nothing.

`daily_plan_items.completed_at` is the fix: the plan records when its own item
was finished, and `learning_service.award_topic_completion` writes it as part of
passing a level. Items frozen before this column exists carry NULL and fall back
to the old rule, which is correct for every one of them that is not a revisit.

Revision ID: b2e5c07d31af
Revises: a1e6f30b95c7
"""

from alembic import op
import sqlalchemy as sa


revision: str = "b2e5c07d31af"
down_revision: str | None = "a1e6f30b95c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_plan_items") as batch:
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_plan_items") as batch:
        batch.drop_column("completed_at")
