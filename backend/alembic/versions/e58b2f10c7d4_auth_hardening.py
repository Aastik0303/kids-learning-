"""auth throttling and password resets

Revision ID: e58b2f10c7d4
Revises: c41d8e77a903
Create Date: 2026-08-23 19:05:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'e58b2f10c7d4'
down_revision: str | None = 'c41d8e77a903'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'auth_throttle',
        sa.Column('key', sa.String(length=200), nullable=False),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('window_started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('key', name=op.f('pk_auth_throttle')),
    )
    op.create_table(
        'password_resets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('parent_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['parent_id'], ['parents.id'], name=op.f('fk_password_resets_parent_id_parents'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_password_resets')),
        sa.UniqueConstraint('token_hash', name=op.f('uq_password_resets_token_hash')),
    )
    op.create_index('ix_password_resets_parent', 'password_resets', ['parent_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_password_resets_parent', table_name='password_resets')
    op.drop_table('password_resets')
    op.drop_table('auth_throttle')
