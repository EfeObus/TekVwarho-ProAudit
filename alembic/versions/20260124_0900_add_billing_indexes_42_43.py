"""Add billing indexes for issues #42 and #43

Revision ID: 20260124_0900
Revises: 20260123_2200
Create Date: 2026-01-24 09:00:00.000000

This migration adds indexes to improve billing query performance:
- UsageRecord: indexes on period_start and period_end for date range queries (#42)
- PaymentTransaction: indexes on paid_at and created_at for reporting (#43)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260124_0900'
down_revision: Union[str, None] = '20260123_2200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Issue #42 - Add indexes to UsageRecord date columns for billing queries
    op.create_index(
        'ix_usage_records_period_start',
        'usage_records',
        ['period_start'],
        unique=False
    )
    op.create_index(
        'ix_usage_records_period_end',
        'usage_records',
        ['period_end'],
        unique=False
    )
    
    # Issue #43 - Add indexes to PaymentTransaction timestamp columns for reporting
    # Note: Using existing columns paid_at and created_at for transaction date queries
    op.create_index(
        'ix_payment_transactions_paid_at',
        'payment_transactions',
        ['paid_at'],
        unique=False
    )
    op.create_index(
        'ix_payment_transactions_created_at',
        'payment_transactions',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    # Remove PaymentTransaction indexes
    op.drop_index('ix_payment_transactions_created_at', table_name='payment_transactions')
    op.drop_index('ix_payment_transactions_paid_at', table_name='payment_transactions')
    
    # Remove UsageRecord indexes
    op.drop_index('ix_usage_records_period_end', table_name='usage_records')
    op.drop_index('ix_usage_records_period_start', table_name='usage_records')
