"""Add FX multi-currency fields to Invoice and Transaction models

Revision ID: 20260127_0900_fx_fields
Revises: 20260126_2000
Create Date: 2026-01-27 09:00:00.000000

IAS 21 Compliance: Effects of Changes in Foreign Exchange Rates
- Original currency tracking for all transactions
- Exchange rate at booking date
- Functional currency (NGN) amounts for financial reporting
- Realized and unrealized FX gain/loss tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260127_0900_fx_fields'
down_revision = '20260126_2000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add FX multi-currency fields to invoices and transactions tables."""
    
    # ===========================================
    # INVOICE TABLE - Multi-Currency Support
    # ===========================================
    
    # Currency and exchange rate fields
    op.add_column('invoices', sa.Column(
        'currency', 
        sa.String(3), 
        nullable=False, 
        server_default='NGN',
        comment='Invoice currency code (e.g., USD, EUR, GBP, NGN)'
    ))
    
    op.add_column('invoices', sa.Column(
        'exchange_rate', 
        sa.Numeric(precision=12, scale=6), 
        nullable=False, 
        server_default='1.000000',
        comment='Exchange rate at invoice date: 1 FC = X NGN'
    ))
    
    op.add_column('invoices', sa.Column(
        'exchange_rate_source', 
        sa.String(50), 
        nullable=True,
        comment='Rate source: CBN, manual, spot, contract'
    ))
    
    # Functional currency amounts (NGN)
    op.add_column('invoices', sa.Column(
        'functional_subtotal', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Subtotal converted to NGN at booking rate'
    ))
    
    op.add_column('invoices', sa.Column(
        'functional_vat_amount', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='VAT converted to NGN at booking rate'
    ))
    
    op.add_column('invoices', sa.Column(
        'functional_total_amount', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Total converted to NGN at booking rate'
    ))
    
    op.add_column('invoices', sa.Column(
        'functional_amount_paid', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Amount paid converted to NGN (may differ due to FX gain/loss)'
    ))
    
    # FX gain/loss tracking
    op.add_column('invoices', sa.Column(
        'realized_fx_gain_loss', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Realized FX gain/loss on payments received'
    ))
    
    op.add_column('invoices', sa.Column(
        'unrealized_fx_gain_loss', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Unrealized FX gain/loss at reporting date'
    ))
    
    op.add_column('invoices', sa.Column(
        'last_revaluation_date', 
        sa.Date(), 
        nullable=True,
        comment='Last FX revaluation date for this invoice'
    ))
    
    op.add_column('invoices', sa.Column(
        'last_revaluation_rate', 
        sa.Numeric(precision=12, scale=6), 
        nullable=True,
        comment='Exchange rate used in last revaluation'
    ))
    
    # ===========================================
    # TRANSACTION TABLE - Multi-Currency Support
    # ===========================================
    
    # Currency and exchange rate fields
    op.add_column('transactions', sa.Column(
        'currency', 
        sa.String(3), 
        nullable=False, 
        server_default='NGN',
        comment='Transaction currency code (e.g., USD, EUR, GBP, NGN)'
    ))
    
    op.add_column('transactions', sa.Column(
        'exchange_rate', 
        sa.Numeric(precision=12, scale=6), 
        nullable=False, 
        server_default='1.000000',
        comment='Exchange rate at transaction date: 1 FC = X NGN'
    ))
    
    op.add_column('transactions', sa.Column(
        'exchange_rate_source', 
        sa.String(50), 
        nullable=True,
        comment='Rate source: CBN, manual, spot, contract'
    ))
    
    # Functional currency amounts (NGN)
    op.add_column('transactions', sa.Column(
        'functional_amount', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Base amount converted to NGN at booking rate'
    ))
    
    op.add_column('transactions', sa.Column(
        'functional_vat_amount', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='VAT converted to NGN at booking rate'
    ))
    
    op.add_column('transactions', sa.Column(
        'functional_total_amount', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Total converted to NGN at booking rate'
    ))
    
    # FX gain/loss tracking
    op.add_column('transactions', sa.Column(
        'realized_fx_gain_loss', 
        sa.Numeric(precision=18, scale=2), 
        nullable=False, 
        server_default='0.00',
        comment='Realized FX gain/loss on settlement'
    ))
    
    op.add_column('transactions', sa.Column(
        'settlement_exchange_rate', 
        sa.Numeric(precision=12, scale=6), 
        nullable=True,
        comment='Exchange rate at payment/settlement'
    ))
    
    op.add_column('transactions', sa.Column(
        'settlement_date', 
        sa.Date(), 
        nullable=True,
        comment='Date of payment/settlement'
    ))
    
    # ===========================================
    # INDEXES for FX queries
    # ===========================================
    
    # Index for foreign currency invoices (for FX revaluation queries)
    op.create_index(
        'ix_invoices_currency',
        'invoices',
        ['currency'],
        unique=False
    )
    
    # Index for foreign currency transactions
    op.create_index(
        'ix_transactions_currency',
        'transactions',
        ['currency'],
        unique=False
    )
    
    # Composite index for FX revaluation batch processing
    op.create_index(
        'ix_invoices_fx_revaluation',
        'invoices',
        ['entity_id', 'currency', 'status'],
        unique=False
    )
    
    # ===========================================
    # MIGRATE EXISTING DATA
    # ===========================================
    # Set functional amounts equal to original amounts for existing NGN records
    
    op.execute("""
        UPDATE invoices 
        SET functional_subtotal = subtotal,
            functional_vat_amount = vat_amount,
            functional_total_amount = total_amount,
            functional_amount_paid = amount_paid
        WHERE currency = 'NGN'
    """)
    
    op.execute("""
        UPDATE transactions 
        SET functional_amount = amount,
            functional_vat_amount = vat_amount,
            functional_total_amount = total_amount
        WHERE currency = 'NGN'
    """)


def downgrade() -> None:
    """Remove FX multi-currency fields from invoices and transactions tables."""
    
    # Drop indexes
    op.drop_index('ix_invoices_fx_revaluation', table_name='invoices')
    op.drop_index('ix_transactions_currency', table_name='transactions')
    op.drop_index('ix_invoices_currency', table_name='invoices')
    
    # Drop invoice FX columns
    op.drop_column('invoices', 'last_revaluation_rate')
    op.drop_column('invoices', 'last_revaluation_date')
    op.drop_column('invoices', 'unrealized_fx_gain_loss')
    op.drop_column('invoices', 'realized_fx_gain_loss')
    op.drop_column('invoices', 'functional_amount_paid')
    op.drop_column('invoices', 'functional_total_amount')
    op.drop_column('invoices', 'functional_vat_amount')
    op.drop_column('invoices', 'functional_subtotal')
    op.drop_column('invoices', 'exchange_rate_source')
    op.drop_column('invoices', 'exchange_rate')
    op.drop_column('invoices', 'currency')
    
    # Drop transaction FX columns
    op.drop_column('transactions', 'settlement_date')
    op.drop_column('transactions', 'settlement_exchange_rate')
    op.drop_column('transactions', 'realized_fx_gain_loss')
    op.drop_column('transactions', 'functional_total_amount')
    op.drop_column('transactions', 'functional_vat_amount')
    op.drop_column('transactions', 'functional_amount')
    op.drop_column('transactions', 'exchange_rate_source')
    op.drop_column('transactions', 'exchange_rate')
    op.drop_column('transactions', 'currency')
