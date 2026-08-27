"""The AI Teacher stops keeping a score.

The class used to run on points: +2 for a right answer, -1 for a wrong one, and
ten of them to finish a stage. It does not any more. A stage is five questions,
each question is asked, then hinted, then answered for the child, and whether the
level passed is worked out at the end from how many of the five landed - by
`learning_service.award_topic_completion`, out of `topic_correct` /
`topic_answered`, which are untouched by this migration and are still the only
thing upstream of a star.

So two columns go, and nothing reads them any more:

* `playground_sessions.points` - the sitting's running total;
* `playground_turns.points_delta` - what one answer moved it by.

The log keeps `is_correct`, which is the part of a turn that was ever worth
reading back. The downgrade puts the columns back empty; the numbers themselves
are not recoverable, and they described a rule the app no longer has.

Revision ID: a1e6f30b95c7
Revises: f9c2a4d16b83
"""

from alembic import op
import sqlalchemy as sa


revision: str = "a1e6f30b95c7"
down_revision: str | None = "f9c2a4d16b83"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("playground_sessions") as batch:
        batch.drop_column("points")
    with op.batch_alter_table("playground_turns") as batch:
        batch.drop_column("points_delta")


def downgrade() -> None:
    with op.batch_alter_table("playground_turns") as batch:
        batch.add_column(
            sa.Column("points_delta", sa.Integer(), nullable=False, server_default="0")
        )
    with op.batch_alter_table("playground_sessions") as batch:
        batch.add_column(sa.Column("points", sa.Integer(), nullable=False, server_default="0"))
