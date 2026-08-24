"""topic memories under the ORM

Revision ID: c41d8e77a903
Revises: c4d20a7e91f6
Create Date: 2026-08-23 18:40:00.000000

`learning_memory_service` used to create this table itself, by hand, with a
`CREATE TABLE IF NOT EXISTS` on its own psycopg connection. A database that has
already run that app therefore has the table and no migration describing it, so
this creates it only where it is missing and leaves an existing one alone. The
shape below is the shape that module created.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c41d8e77a903'
down_revision: str | None = 'c4d20a7e91f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table('topic_memories'):
        return
    op.create_table(
        'topic_memories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('child_id', sa.Text(), nullable=False),
        sa.Column('subject_id', sa.Text(), nullable=False),
        sa.Column('topic_id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('score BETWEEN 0 AND 100', name=op.f('ck_topic_memories_score_range')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_topic_memories')),
        sa.UniqueConstraint('child_id', 'topic_id', name='uq_topic_memories_child_topic'),
    )
    op.create_index('ix_topic_memories_child_completed', 'topic_memories', ['child_id', 'completed_at'])


def downgrade() -> None:
    if not _has_table('topic_memories'):
        return
    op.drop_index('ix_topic_memories_child_completed', table_name='topic_memories')
    op.drop_table('topic_memories')
