"""google sign-in: a linked account, and a password that may be absent

Revision ID: f1b7c3a2d905
Revises: d8e4b1a05c72
Create Date: 2026-09-13 10:00:00.000000

Two changes to `parents`, and they belong together:

* `google_subject` - Google's stable id for the account, unique so one Google
  account cannot end up behind two parent rows. Null for every account that
  signs in with a password, which is every account that exists today.
* `password_hash` becomes nullable. An account created through Google has no
  password at all, and a placeholder hash in that column would be a password
  nobody can use and nobody can distinguish from one they can.

Nothing existing is rewritten: every current row keeps its hash and gets a null
subject, so no parent is signed out and none of them has to do anything.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f1b7c3a2d905"
down_revision: str | None = "d8e4b1a05c72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Both changes go through `batch_alter_table`. SQLite cannot ALTER a constraint
# or a column's nullability in place at all, and batch mode is Alembic's
# copy-and-move around that; on PostgreSQL it is a plain ALTER. One migration
# has to describe both backends here, because the test suite runs on SQLite and
# production runs on PostgreSQL.


def upgrade() -> None:
    with op.batch_alter_table("parents") as batch:
        batch.add_column(sa.Column("google_subject", sa.String(length=64), nullable=True))
        batch.create_unique_constraint(op.f("uq_parents_google_subject"), ["google_subject"])
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # A row with no password cannot go back into a NOT NULL column, and there
    # is no hash to invent for it. Google-only accounts are deleted rather than
    # silently given a password nobody set.
    op.execute("DELETE FROM parents WHERE password_hash IS NULL")
    with op.batch_alter_table("parents") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
        batch.drop_constraint(op.f("uq_parents_google_subject"), type_="unique")
        batch.drop_column("google_subject")
