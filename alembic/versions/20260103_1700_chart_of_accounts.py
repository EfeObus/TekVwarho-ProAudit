"""Chart of Accounts and General Ledger tables

Revision ID: 20260103_1700_chart_of_accounts
Revises: 20260103_1600_add_fixed_assets
Create Date: 2026-01-03 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260103_1700_chart_of_accounts'
down_revision = '20260118_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create AccountType enum
    account_type_enum = postgresql.ENUM(
        'ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', 'INCOME',
        name='accounttype',
        create_type=False
    )
    account_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create AccountSubType enum (30+ Nigerian accounting subtypes)
    account_subtype_enum = postgresql.ENUM(
        'CASH', 'BANK', 'ACCOUNTS_RECEIVABLE', 'INVENTORY', 'PREPAID_EXPENSE',
        'FIXED_ASSET', 'ACCUMULATED_DEPRECIATION', 'OTHER_CURRENT_ASSET',
        'OTHER_NON_CURRENT_ASSET', 'ACCOUNTS_PAYABLE', 'ACCRUED_EXPENSE',
        'VAT_PAYABLE', 'WHT_PAYABLE', 'PAYE_PAYABLE', 'PENSION_PAYABLE',
        'LOAN', 'OTHER_CURRENT_LIABILITY', 'OTHER_NON_CURRENT_LIABILITY',
        'SHARE_CAPITAL', 'RETAINED_EARNINGS', 'DRAWINGS', 'OTHER_EQUITY',
        'SALES_REVENUE', 'SERVICE_REVENUE', 'INTEREST_INCOME', 'OTHER_INCOME',
        'COST_OF_GOODS_SOLD', 'SALARY_EXPENSE', 'RENT_EXPENSE', 'UTILITIES_EXPENSE',
        'DEPRECIATION_EXPENSE', 'BANK_CHARGES', 'TAX_EXPENSE', 'OTHER_EXPENSE',
        name='accountsubtype',
        create_type=False
    )
    account_subtype_enum.create(op.get_bind(), checkfirst=True)
    
    # Create NormalBalance enum
    normal_balance_enum = postgresql.ENUM(
        'DEBIT', 'CREDIT',
        name='normalbalance',
        create_type=False
    )
    normal_balance_enum.create(op.get_bind(), checkfirst=True)
    
    # Create FiscalPeriodStatus enum
    period_status_enum = postgresql.ENUM(
        'OPEN', 'CLOSED', 'LOCKED', 'REOPENED', 'YEAR_END',
        name='fiscalperiodstatus',
        create_type=False
    )
    period_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create JournalEntryStatus enum
    entry_status_enum = postgresql.ENUM(
        'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'POSTED', 'REJECTED', 'REVERSED', 'VOIDED',
        name='journalentrystatus',
        create_type=False
    )
    entry_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create JournalEntryType enum
    entry_type_enum = postgresql.ENUM(
        'MANUAL', 'SALES', 'PURCHASE', 'RECEIPT', 'PAYMENT', 'PAYROLL',
        'DEPRECIATION', 'AMORTIZATION', 'ACCRUAL', 'ADJUSTMENT', 'CLOSING',
        'OPENING', 'REVERSAL', 'TAX_ADJUSTMENT', 'BANK_RECONCILIATION',
        'INVENTORY_ADJUSTMENT', 'INTERCOMPANY',
        name='journalentrytype',
        create_type=False
    )
    entry_type_enum.create(op.get_bind(), checkfirst=True)
    
    # =========================================================================
    # CHART OF ACCOUNTS TABLE
    # =========================================================================
    op.create_table(
        'chart_of_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Account Identification
        sa.Column('account_code', sa.String(20), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        
        # Account Classification
        sa.Column('account_type', postgresql.ENUM('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', 'INCOME', name='accounttype', create_type=False), nullable=False, index=True),
        sa.Column('account_sub_type', postgresql.ENUM(name='accountsubtype', create_type=False), nullable=True),
        sa.Column('normal_balance', postgresql.ENUM('DEBIT', 'CREDIT', name='normalbalance', create_type=False), nullable=False),
        
        # Hierarchy
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chart_of_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('level', sa.Integer, nullable=False, default=1),
        sa.Column('is_header', sa.Boolean, nullable=False, default=False),
        
        # Balances
        sa.Column('opening_balance', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('opening_balance_date', sa.Date, nullable=True),
        sa.Column('current_balance', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('ytd_debit', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('ytd_credit', sa.Numeric(18, 2), nullable=False, default=0),
        
        # Bank Linking
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bank_accounts.id', ondelete='SET NULL'), nullable=True),
        
        # Tax Integration
        sa.Column('is_tax_account', sa.Boolean, nullable=False, default=False),
        sa.Column('tax_type', sa.String(50), nullable=True),
        sa.Column('tax_rate', sa.Numeric(5, 2), nullable=True),
        
        # Flags
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('is_system_account', sa.Boolean, nullable=False, default=False),
        sa.Column('is_reconcilable', sa.Boolean, nullable=False, default=False),
        sa.Column('allow_manual_entries', sa.Boolean, nullable=False, default=True),
        sa.Column('cash_flow_category', sa.String(50), nullable=True),
        sa.Column('sort_order', sa.Integer, nullable=True),
        
        # Audit Trail
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        
        # Unique Constraint
        sa.UniqueConstraint('entity_id', 'account_code', name='uq_chart_of_accounts_entity_code'),
    )
    
    # Create indexes
    op.create_index('ix_chart_of_accounts_parent', 'chart_of_accounts', ['parent_id'])
    op.create_index('ix_chart_of_accounts_code', 'chart_of_accounts', ['account_code'])
    
    # =========================================================================
    # FISCAL YEARS TABLE
    # =========================================================================
    op.create_table(
        'fiscal_years',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('year_name', sa.String(50), nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('is_current', sa.Boolean, nullable=False, default=False),
        sa.Column('is_closed', sa.Boolean, nullable=False, default=False),
        sa.Column('closed_at', sa.DateTime, nullable=True),
        sa.Column('closed_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        
        # Audit Trail
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        
        sa.UniqueConstraint('entity_id', 'year_name', name='uq_fiscal_years_entity_name'),
    )
    
    # =========================================================================
    # FISCAL PERIODS TABLE
    # =========================================================================
    op.create_table(
        'fiscal_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('fiscal_year_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fiscal_years.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('period_name', sa.String(50), nullable=False),
        sa.Column('period_number', sa.Integer, nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('status', postgresql.ENUM(name='fiscalperiodstatus', create_type=False), nullable=False, default='OPEN'),
        
        # Close Information
        sa.Column('closed_at', sa.DateTime, nullable=True),
        sa.Column('closed_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('closing_notes', sa.Text, nullable=True),
        
        # Reconciliation Status
        sa.Column('bank_reconciled', sa.Boolean, nullable=False, default=False),
        sa.Column('inventory_counted', sa.Boolean, nullable=False, default=False),
        sa.Column('ar_reconciled', sa.Boolean, nullable=False, default=False),
        sa.Column('ap_reconciled', sa.Boolean, nullable=False, default=False),
        
        # Audit Trail
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        
        sa.UniqueConstraint('fiscal_year_id', 'period_number', name='uq_fiscal_periods_year_number'),
    )
    
    # =========================================================================
    # JOURNAL ENTRIES TABLE
    # =========================================================================
    op.create_table(
        'journal_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('fiscal_period_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fiscal_periods.id'), nullable=True),
        
        # Entry Identification
        sa.Column('entry_number', sa.String(30), nullable=False),
        sa.Column('entry_date', sa.Date, nullable=False, index=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('memo', sa.Text, nullable=True),
        
        # Entry Type & Source
        sa.Column('entry_type', postgresql.ENUM(name='journalentrytype', create_type=False), nullable=False, default='MANUAL'),
        sa.Column('source_module', sa.String(50), nullable=True),
        sa.Column('source_document_type', sa.String(50), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_reference', sa.String(100), nullable=True),
        
        # Amounts
        sa.Column('total_debit', sa.Numeric(18, 2), nullable=False),
        sa.Column('total_credit', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='NGN'),
        sa.Column('exchange_rate', sa.Numeric(18, 6), nullable=False, default=1),
        
        # Status & Approval
        sa.Column('status', postgresql.ENUM(name='journalentrystatus', create_type=False), nullable=False, default='DRAFT'),
        sa.Column('requires_approval', sa.Boolean, nullable=False, default=False),
        sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('posted_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('posted_at', sa.DateTime, nullable=True),
        
        # Reversal Information
        sa.Column('is_reversed', sa.Boolean, nullable=False, default=False),
        sa.Column('reversed_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reversed_at', sa.DateTime, nullable=True),
        sa.Column('reversal_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('original_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reversal_reason', sa.String(500), nullable=True),
        
        # Bank Reconciliation Link
        sa.Column('reconciliation_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Recurring Entry
        sa.Column('is_recurring', sa.Boolean, nullable=False, default=False),
        sa.Column('recurring_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Audit Trail
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        
        sa.UniqueConstraint('entity_id', 'entry_number', name='uq_journal_entries_entity_number'),
    )
    
    # =========================================================================
    # JOURNAL ENTRY LINES TABLE
    # =========================================================================
    op.create_table(
        'journal_entry_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('journal_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chart_of_accounts.id'), nullable=False, index=True),
        
        sa.Column('line_number', sa.Integer, nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        
        # Amounts (one must be zero)
        sa.Column('debit_amount', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('credit_amount', sa.Numeric(18, 2), nullable=False, default=0),
        
        # Dimensions (for departmental/project accounting)
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('cost_center_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Tax Information
        sa.Column('tax_code', sa.String(20), nullable=True),
        sa.Column('tax_amount', sa.Numeric(18, 2), nullable=True),
        
        # References
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('bank_transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Audit Trail
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # =========================================================================
    # ACCOUNT BALANCES TABLE (Denormalized for Performance)
    # =========================================================================
    op.create_table(
        'account_balances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chart_of_accounts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('fiscal_period_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fiscal_periods.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('opening_balance', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('period_debit', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('period_credit', sa.Numeric(18, 2), nullable=False, default=0),
        sa.Column('closing_balance', sa.Numeric(18, 2), nullable=False, default=0),
        
        sa.Column('last_calculated_at', sa.DateTime, nullable=True),
        
        sa.UniqueConstraint('account_id', 'fiscal_period_id', name='uq_account_balances_account_period'),
    )
    
    # =========================================================================
    # RECURRING JOURNAL ENTRIES TABLE
    # =========================================================================
    op.create_table(
        'recurring_journal_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('template_data', postgresql.JSONB, nullable=False),
        
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=True),
        sa.Column('next_run_date', sa.Date, nullable=True),
        sa.Column('last_run_date', sa.Date, nullable=True),
        sa.Column('run_count', sa.Integer, nullable=False, default=0),
        
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('auto_post', sa.Boolean, nullable=False, default=False),
        
        # Audit Trail
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    
    # =========================================================================
    # GL INTEGRATION LOG TABLE
    # =========================================================================
    op.create_table(
        'gl_integration_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('source_module', sa.String(50), nullable=False),
        sa.Column('source_document_type', sa.String(50), nullable=False),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_reference', sa.String(100), nullable=True),
        
        sa.Column('journal_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journal_entries.id', ondelete='SET NULL'), nullable=True),
        
        sa.Column('is_reversed', sa.Boolean, nullable=False, default=False),
        sa.Column('reversal_log_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('posted_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('posted_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        
        sa.UniqueConstraint('entity_id', 'source_module', 'source_document_type', 'source_document_id', name='uq_gl_integration_source'),
    )
    
    # Create indexes for GL Integration
    op.create_index('ix_gl_integration_source', 'gl_integration_logs', ['source_module', 'source_document_type'])


def downgrade() -> None:
    op.drop_table('gl_integration_logs')
    op.drop_table('recurring_journal_entries')
    op.drop_table('account_balances')
    op.drop_table('journal_entry_lines')
    op.drop_table('journal_entries')
    op.drop_table('fiscal_periods')
    op.drop_table('fiscal_years')
    op.drop_table('chart_of_accounts')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS journalentrytype')
    op.execute('DROP TYPE IF EXISTS journalentrystatus')
    op.execute('DROP TYPE IF EXISTS fiscalperiodstatus')
    op.execute('DROP TYPE IF EXISTS normalbalance')
    op.execute('DROP TYPE IF EXISTS accountsubtype')
    op.execute('DROP TYPE IF EXISTS accounttype')
