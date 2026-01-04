"""Add must_reset_password column to users table

Revision ID: 20260104_0930
Revises: 20260103_1700_add_missing_2026_columns
Create Date: 2026-01-04 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260104_0930'
down_revision = '20260103_1700_add_missing_2026_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add must_reset_password column to users table."""
    # Add must_reset_password column
    op.add_column(
        'users',
        sa.Column(
            'must_reset_password',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Force password reset on next login (for newly onboarded staff)'
        )
    )


def downgrade() -> None:
    """Remove must_reset_password column from users table."""
    op.drop_column('users', 'must_reset_password')
