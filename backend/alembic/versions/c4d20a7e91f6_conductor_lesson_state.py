"""conductor lesson state

Revision ID: c4d20a7e91f6
Revises: f3a91c7d52b0
Create Date: 2026-08-23 17:40:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d20a7e91f6'
down_revision: str | None = 'f3a91c7d52b0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The lesson state stops being a resume point and becomes the live class: the
# phase, the ladder, the attempt count and the watcher counters the Branch
# Decision Engine reads. Every column carries a server default, so a child who
# was mid-topic when this ships becomes a valid conductor state rather than a
# row full of nulls.
NEW_COLUMNS = (
    ("phase", sa.String(length=16), "'greet'"),
    ("current_skill_id", sa.String(length=64), "''"),
    ("ladder_rung", sa.Integer(), "0"),
    ("attempts_on_current", sa.Integer(), "0"),
    ("consecutive_correct", sa.Integer(), "0"),
    ("frustration_score", sa.Float(), "0"),
    ("modality", sa.String(length=8), "'tap'"),
    ("idle_rung", sa.Integer(), "0"),
    ("correct_count", sa.Integer(), "0"),
    ("retry_burst_count", sa.Integer(), "0"),
    ("unresolved_speech", sa.Integer(), "0"),
    ("speech_attempts", sa.Integer(), "0"),
    ("idle_rungs_hit", sa.Integer(), "0"),
)

JSON_COLUMNS = (
    ("explanations_used", "'[]'"),
    ("activity_ids", "'[]'"),
    ("recent_answers", "'[]'"),
)


def upgrade() -> None:
    with op.batch_alter_table('lesson_states', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.String(length=64), nullable=True))
        for name, column_type, default in NEW_COLUMNS:
            batch_op.add_column(
                sa.Column(name, column_type, nullable=False, server_default=sa.text(default))
            )
        for name, default in JSON_COLUMNS:
            batch_op.add_column(
                sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text(default))
            )
        batch_op.add_column(sa.Column('paused_for', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('resume_payload', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            )
        )
        batch_op.add_column(sa.Column('last_input_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_unique_constraint(op.f('uq_lesson_states_session_id'), ['session_id'])
        batch_op.create_index('ix_lesson_states_child_updated', ['child_id', 'updated_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('lesson_states', schema=None) as batch_op:
        batch_op.drop_index('ix_lesson_states_child_updated')
        batch_op.drop_constraint(op.f('uq_lesson_states_session_id'), type_='unique')
        for name in ('last_input_at', 'started_at', 'resume_payload', 'paused_for'):
            batch_op.drop_column(name)
        for name, _ in JSON_COLUMNS:
            batch_op.drop_column(name)
        for name, _, _ in NEW_COLUMNS:
            batch_op.drop_column(name)
        batch_op.drop_column('session_id')
