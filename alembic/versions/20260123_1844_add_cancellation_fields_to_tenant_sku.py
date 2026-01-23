"""add_cancellation_fields_to_tenant_sku

Revision ID: 0563e1dd3aeb
Revises: 20260122_1920
Create Date: 2026-01-23 18:44:35.238127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0563e1dd3aeb'
down_revision: Union[str, None] = '20260122_1920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cancel_at_period_end field
    op.add_column(
        'tenant_skus',
        sa.Column(
            'cancel_at_period_end',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='If True, subscription will be cancelled/downgraded at end of current period'
        )
    )
    
    # Add cancellation_requested_at field
    op.add_column(
        'tenant_skus',
        sa.Column(
            'cancellation_requested_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When cancellation was requested'
        )
    )
    
    # Add cancellation_reason field
    op.add_column(
        'tenant_skus',
        sa.Column(
            'cancellation_reason',
            sa.String(500),
            nullable=True,
            comment='Reason for cancellation'
        )
    )
    
    # Create the SKUTier enum type if it doesn't exist (for scheduled_downgrade_tier)
    # Check if enum already exists before creating
    sku_tier_enum = postgresql.ENUM(
        'CORE', 'PROFESSIONAL', 'ENTERPRISE',
        name='skutier',
        create_type=False
    )
    
    # Add scheduled_downgrade_tier field
    op.add_column(
        'tenant_skus',
        sa.Column(
            'scheduled_downgrade_tier',
            sku_tier_enum,
            nullable=True,
            comment='Tier to downgrade to at period end (usually CORE)'
        )
    )


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column('tenant_skus', 'scheduled_downgrade_tier')
    op.drop_column('tenant_skus', 'cancellation_reason')
    op.drop_column('tenant_skus', 'cancellation_requested_at')
    op.drop_column('tenant_skus', 'cancel_at_period_end')
