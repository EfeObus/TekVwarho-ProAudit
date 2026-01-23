"""Add payment_transactions table for tracking Paystack payments

Revision ID: 20260122_1920
Revises: 20260120_1000
Create Date: 2026-01-22 19:20:00.000000

This migration adds:
- payment_transactions: Full payment tracking for Paystack transactions
  - Stores all payment attempts, successes, and failures
  - Links to organizations for billing
  - Tracks card details, fees, and Paystack responses
  - Supports full audit trail for financial compliance

Fields include:
- Transaction identifiers (reference, paystack_reference, access_code)
- Status tracking (pending, processing, success, failed, etc.)
- Amount details (amount_kobo, currency, fee_kobo)
- Payment method info (channel, card_type, last4, bank)
- SKU/billing context (tier, billing_cycle, intelligence_addon)
- Timestamps (created_at, paid_at, verified_at, refunded_at)
- Full Paystack API response storage for debugging
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '20260122_1920'
down_revision = '20260120_1000'
branch_labels = None
depends_on = None


# ENUM for payment status
payment_status_enum = postgresql.ENUM(
    'pending', 'processing', 'success', 'failed', 
    'cancelled', 'refunded', 'partially_refunded', 'disputed',
    name='paymentstatus',
    create_type=False
)

# ENUM for transaction type
transaction_type_enum = postgresql.ENUM(
    'payment', 'subscription', 'addon', 'upgrade', 'renewal', 'refund',
    name='transactiontype',
    create_type=False
)


def upgrade() -> None:
    # Create ENUM types first
    payment_status_enum.create(op.get_bind(), checkfirst=True)
    transaction_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create payment_transactions table
    op.create_table(
        'payment_transactions',
        # Primary key and timestamps
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        
        # Foreign keys
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('tenant_sku_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant_skus.id', ondelete='SET NULL'), nullable=True),
        
        # Transaction identifiers
        sa.Column('reference', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('paystack_reference', sa.String(100), nullable=True, unique=True),
        sa.Column('paystack_access_code', sa.String(100), nullable=True),
        sa.Column('authorization_url', sa.Text, nullable=True),
        
        # Transaction details
        sa.Column('transaction_type', transaction_type_enum, default='payment', nullable=False),
        sa.Column('status', payment_status_enum, default='pending', nullable=False, index=True),
        sa.Column('amount_kobo', sa.BigInteger, nullable=False),
        sa.Column('currency', sa.String(3), default='NGN', nullable=False),
        sa.Column('fee_kobo', sa.BigInteger, nullable=True),
        
        # SKU/Billing context
        sa.Column('tier', sa.String(20), nullable=True),
        sa.Column('billing_cycle', sa.String(20), nullable=True),
        sa.Column('intelligence_addon', sa.String(20), nullable=True),
        sa.Column('additional_users', sa.Integer, default=0),
        
        # Payment method details
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('channel', sa.String(50), nullable=True),
        sa.Column('card_type', sa.String(50), nullable=True),
        sa.Column('card_last4', sa.String(4), nullable=True),
        sa.Column('card_exp_month', sa.String(2), nullable=True),
        sa.Column('card_exp_year', sa.String(4), nullable=True),
        sa.Column('card_bank', sa.String(100), nullable=True),
        sa.Column('card_brand', sa.String(50), nullable=True),
        
        # Customer info
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_code', sa.String(100), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        
        # Callback/webhook info
        sa.Column('callback_url', sa.Text, nullable=True),
        sa.Column('webhook_event_id', sa.String(100), nullable=True),
        sa.Column('webhook_received_at', sa.DateTime(timezone=True), nullable=True),
        
        # Response storage
        sa.Column('gateway_response', sa.String(500), nullable=True),
        sa.Column('paystack_response', postgresql.JSONB, nullable=True),
        sa.Column('custom_metadata', postgresql.JSONB, nullable=True),
        
        # Timestamps
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refund_amount_kobo', sa.BigInteger, nullable=True),
        
        # Error tracking
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
        
        # Notes
        sa.Column('notes', sa.Text, nullable=True),
    )
    
    # Create indexes for common queries
    op.create_index(
        'ix_payment_transactions_org_created',
        'payment_transactions',
        ['organization_id', 'created_at'],
    )
    op.create_index(
        'ix_payment_transactions_status_created',
        'payment_transactions',
        ['status', 'created_at'],
    )
    op.create_index(
        'ix_payment_transactions_customer_email',
        'payment_transactions',
        ['customer_email'],
    )


def downgrade() -> None:
    # Drop table
    op.drop_table('payment_transactions')
    
    # Drop ENUM types
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
    transaction_type_enum.drop(op.get_bind(), checkfirst=True)
