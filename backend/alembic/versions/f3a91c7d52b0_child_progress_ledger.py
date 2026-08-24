"""child progress ledger

Revision ID: f3a91c7d52b0
Revises: 2cded3bcb9a8
Create Date: 2026-08-23 15:10:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a91c7d52b0'
down_revision: str | None = '2cded3bcb9a8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'child_progress',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('child_id', sa.Uuid(), nullable=False),
        sa.Column('state', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['child_id'], ['children.id'], name=op.f('fk_child_progress_child_id_children'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_child_progress')),
        sa.UniqueConstraint('child_id', name=op.f('uq_child_progress_child_id')),
    )


def downgrade() -> None:
    op.drop_table('child_progress')
