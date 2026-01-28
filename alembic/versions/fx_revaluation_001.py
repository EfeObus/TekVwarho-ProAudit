"""Add FX revaluation tables for multi-currency support

Revision ID: fx_revaluation_001
Revises: 20260128_1000
Create Date: 2026-01-27

Adds:
- fx_revaluations: Track realized and unrealized FX gains/losses
- fx_exposure_summaries: Summary of FX exposure by currency
- Updates JournalEntryType enum with FX types
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'fx_revaluation_001'
down_revision = '20260128_1000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create FX revaluation type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fxrevaluationtype AS ENUM ('realized', 'unrealized', 'settlement');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create FX account type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fxaccounttype AS ENUM ('bank', 'receivable', 'payable', 'loan', 'intercompany');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Add new values to journal entry type enum
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE journalentrytype ADD VALUE IF NOT EXISTS 'fx_revaluation';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE journalentrytype ADD VALUE IF NOT EXISTS 'fx_realized_gain_loss';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE journalentrytype ADD VALUE IF NOT EXISTS 'fx_unrealized_gain_loss';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create fx_revaluations table
    op.create_table(
        'fx_revaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('revaluation_date', sa.Date, nullable=False),
        sa.Column('revaluation_type', postgresql.ENUM('realized', 'unrealized', 'settlement', name='fxrevaluationtype', create_type=False), nullable=False),
        
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chart_of_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fx_account_type', postgresql.ENUM('bank', 'receivable', 'payable', 'loan', 'intercompany', name='fxaccounttype', create_type=False), nullable=False),
        
        sa.Column('foreign_currency', sa.String(3), nullable=False),
        sa.Column('functional_currency', sa.String(3), nullable=False, server_default='NGN'),
        
        sa.Column('original_fc_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('original_exchange_rate', sa.Numeric(12, 6), nullable=False),
        sa.Column('original_ngn_amount', sa.Numeric(18, 2), nullable=False),
        
        sa.Column('revaluation_rate', sa.Numeric(12, 6), nullable=False),
        sa.Column('revalued_ngn_amount', sa.Numeric(18, 2), nullable=False),
        
        sa.Column('fx_gain_loss', sa.Numeric(18, 2), nullable=False),
        sa.Column('is_gain', sa.Boolean, nullable=False),
        
        sa.Column('journal_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journal_entries.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_document_type', sa.String(50), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('fiscal_period_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fiscal_periods.id', ondelete='SET NULL'), nullable=True),
        
        sa.Column('notes', sa.Text, nullable=True),
    )
    
    op.create_index('ix_fx_reval_entity_date', 'fx_revaluations', ['entity_id', 'revaluation_date'])
    op.create_index('ix_fx_reval_account', 'fx_revaluations', ['account_id', 'revaluation_date'])
    op.create_index('ix_fx_reval_type', 'fx_revaluations', ['revaluation_type', 'revaluation_date'])
    
    # Create fx_exposure_summaries table
    op.create_table(
        'fx_exposure_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('as_of_date', sa.Date, nullable=False),
        sa.Column('foreign_currency', sa.String(3), nullable=False),
        
        sa.Column('bank_fc_balance', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('receivable_fc_balance', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('payable_fc_balance', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('loan_fc_balance', sa.Numeric(18, 2), nullable=False, server_default='0'),
        
        sa.Column('net_fc_exposure', sa.Numeric(18, 2), nullable=False),
        sa.Column('current_rate', sa.Numeric(12, 6), nullable=False),
        sa.Column('net_ngn_exposure', sa.Numeric(18, 2), nullable=False),
        
        sa.Column('ytd_realized_gain_loss', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('ytd_unrealized_gain_loss', sa.Numeric(18, 2), nullable=False, server_default='0'),
        
        sa.UniqueConstraint('entity_id', 'as_of_date', 'foreign_currency', name='uq_fx_exposure_date_currency'),
    )
    
    op.create_index('ix_fx_exposure_entity', 'fx_exposure_summaries', ['entity_id', 'as_of_date'])
    
    # Add currency column to chart_of_accounts if not exists
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE chart_of_accounts ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'NGN';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)


def downgrade() -> None:
    op.drop_table('fx_exposure_summaries')
    op.drop_table('fx_revaluations')
    
    op.execute("DROP TYPE IF EXISTS fxaccounttype")
    op.execute("DROP TYPE IF EXISTS fxrevaluationtype")
