"""the emailed sign-in code: a challenge waiting to be finished

Revision ID: a3d9f2e71c48
Revises: f1b7c3a2d905
Create Date: 2026-09-13 12:00:00.000000

One table. A row is a sign-in whose password has been accepted and which is
waiting on the code emailed to the account's address; it holds no session and
cannot be turned into one.

Neither secret is stored as itself: the handle the client carries and the code
the parent types are both keyed hashes, so a dump of this table is not a drawer
full of sign-ins in progress. `attempts` is what keeps six digits worth having.

Nothing existing is touched, and nobody is signed out: sessions already open
stay open, because a session that already exists was never the thing this
protects.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a3d9f2e71c48"
down_revision: str | None = "f1b7c3a2d905"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sign_in_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=False),
        sa.Column("challenge_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sends", sa.Integer(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["parents.id"],
            name=op.f("fk_sign_in_challenges_parent_id_parents"),
            # The challenge goes with the account. A row pointing at a deleted
            # parent is a sign-in for somebody who does not exist.
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sign_in_challenges")),
        sa.UniqueConstraint("challenge_hash", name=op.f("uq_sign_in_challenges_challenge_hash")),
    )
    op.create_index(
        op.f("ix_sign_in_challenges_parent"), "sign_in_challenges", ["parent_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sign_in_challenges_parent"), table_name="sign_in_challenges")
    op.drop_table("sign_in_challenges")
