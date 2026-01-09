"""Add bank reconciliation and expense claims tables

Revision ID: 20260108_2030
Revises: 91492aec7b35
Create Date: 2026-01-08 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260108_2030'
down_revision = '91492aec7b35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bank Accounts table
    op.create_table('bank_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_name', sa.String(200), nullable=False),
        sa.Column('account_number', sa.String(20), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('bank_code', sa.String(10), nullable=True),
        sa.Column('account_type', sa.String(50), nullable=False, server_default='current'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='NGN'),
        sa.Column('current_balance', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('last_reconciled_date', sa.Date(), nullable=True),
        sa.Column('last_reconciled_balance', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('gl_account_code', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['business_entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bank_accounts_entity_id', 'bank_accounts', ['entity_id'])
    op.create_index('ix_bank_accounts_account_number', 'bank_accounts', ['account_number'])

    # Bank Statements table
    op.create_table('bank_statements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('statement_date', sa.Date(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('opening_balance', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('closing_balance', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('imported_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['imported_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bank_statements_bank_account_id', 'bank_statements', ['bank_account_id'])
    op.create_index('ix_bank_statements_statement_date', 'bank_statements', ['statement_date'])

    # Bank Statement Transactions table
    op.create_table('bank_statement_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('statement_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('value_date', sa.Date(), nullable=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('reference', sa.String(100), nullable=True),
        sa.Column('debit_amount', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('credit_amount', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('running_balance', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('match_status', sa.String(50), nullable=False, server_default='unmatched'),
        sa.Column('matched_transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('matched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('matched_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['statement_id'], ['bank_statements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['matched_transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['matched_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bank_statement_transactions_statement_id', 'bank_statement_transactions', ['statement_id'])
    op.create_index('ix_bank_statement_transactions_match_status', 'bank_statement_transactions', ['match_status'])

    # Bank Reconciliations table
    op.create_table('bank_reconciliations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciliation_date', sa.Date(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('statement_balance', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('book_balance', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('adjusted_statement_balance', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('adjusted_book_balance', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('difference', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('prepared_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prepared_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bank_reconciliations_bank_account_id', 'bank_reconciliations', ['bank_account_id'])
    op.create_index('ix_bank_reconciliations_status', 'bank_reconciliations', ['status'])

    # Expense Claims table
    op.create_table('expense_claims',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('claim_number', sa.String(50), nullable=False),
        sa.Column('claim_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='NGN'),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_reference', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['business_entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rejected_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_number')
    )
    op.create_index('ix_expense_claims_entity_id', 'expense_claims', ['entity_id'])
    op.create_index('ix_expense_claims_employee_id', 'expense_claims', ['employee_id'])
    op.create_index('ix_expense_claims_status', 'expense_claims', ['status'])
    op.create_index('ix_expense_claims_claim_number', 'expense_claims', ['claim_number'])

    # Expense Claim Items table
    op.create_table('expense_claim_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('expense_claim_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='NGN'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('receipt_number', sa.String(100), nullable=True),
        sa.Column('receipt_path', sa.String(500), nullable=True),
        sa.Column('vendor_name', sa.String(200), nullable=True),
        sa.Column('is_tax_deductible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('gl_account_code', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['expense_claim_id'], ['expense_claims.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_expense_claim_items_expense_claim_id', 'expense_claim_items', ['expense_claim_id'])
    op.create_index('ix_expense_claim_items_category', 'expense_claim_items', ['category'])


def downgrade() -> None:
    op.drop_table('expense_claim_items')
    op.drop_table('expense_claims')
    op.drop_table('bank_reconciliations')
    op.drop_table('bank_statement_transactions')
    op.drop_table('bank_statements')
    op.drop_table('bank_accounts')
