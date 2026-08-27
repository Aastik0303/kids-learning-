"""lesson_states.echo_attempts - the say-it-back beat's counter

The conductor now stops after explaining a thing and asks the child to say it
back into the microphone. How many times it has asked on the current activity
is lesson state like any other: held in the row, not in the client, so a phone
that loses its connection mid-question comes back to the same beat rather than
starting the explanation again.

Revision ID: b7f1a2c9d4e3
Revises: e58b2f10c7d4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b7f1a2c9d4e3"
down_revision: str | None = "e58b2f10c7d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lesson_states",
        sa.Column("echo_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("lesson_states", "echo_attempts")
