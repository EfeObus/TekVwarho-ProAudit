"""
Create accounting tables in the database.
Run this script to create the Chart of Accounts and General Ledger tables.
"""

import asyncio
from sqlalchemy import text
from app.database import async_session_factory


async def create_accounting_tables():
    async with async_session_factory() as session:
        # Create chart_of_accounts table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS chart_of_accounts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE CASCADE,
                account_code VARCHAR(20) NOT NULL,
                account_name VARCHAR(255) NOT NULL,
                description TEXT,
                account_type accounttype NOT NULL,
                account_sub_type accountsubtype,
                normal_balance normalbalance NOT NULL,
                parent_id UUID REFERENCES chart_of_accounts(id) ON DELETE SET NULL,
                level INTEGER NOT NULL DEFAULT 1,
                is_header BOOLEAN NOT NULL DEFAULT FALSE,
                opening_balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
                opening_balance_date DATE,
                current_balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
                ytd_debit NUMERIC(18, 2) NOT NULL DEFAULT 0,
                ytd_credit NUMERIC(18, 2) NOT NULL DEFAULT 0,
                bank_account_id UUID REFERENCES bank_accounts(id) ON DELETE SET NULL,
                is_tax_account BOOLEAN NOT NULL DEFAULT FALSE,
                tax_type VARCHAR(50),
                tax_rate NUMERIC(5, 2),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_system_account BOOLEAN NOT NULL DEFAULT FALSE,
                is_reconcilable BOOLEAN NOT NULL DEFAULT FALSE,
                allow_manual_entries BOOLEAN NOT NULL DEFAULT TRUE,
                cash_flow_category VARCHAR(50),
                sort_order INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                created_by_id UUID REFERENCES users(id),
                updated_by_id UUID REFERENCES users(id),
                CONSTRAINT uq_chart_of_accounts_entity_code UNIQUE (entity_id, account_code)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_chart_of_accounts_entity ON chart_of_accounts(entity_id)'))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_chart_of_accounts_type ON chart_of_accounts(account_type)'))
        print('chart_of_accounts table created')
        
        # Create fiscal_years table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS fiscal_years (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE CASCADE,
                year_name VARCHAR(50) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                is_current BOOLEAN NOT NULL DEFAULT FALSE,
                is_closed BOOLEAN NOT NULL DEFAULT FALSE,
                closed_at TIMESTAMP,
                closed_by_id UUID REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT uq_fiscal_years_entity_name UNIQUE (entity_id, year_name)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_fiscal_years_entity ON fiscal_years(entity_id)'))
        print('fiscal_years table created')
        
        # Create fiscal_periods table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS fiscal_periods (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE CASCADE,
                fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE CASCADE,
                period_name VARCHAR(50) NOT NULL,
                period_number INTEGER NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                status fiscalperiodstatus NOT NULL DEFAULT 'OPEN',
                closed_at TIMESTAMP,
                closed_by_id UUID REFERENCES users(id),
                closing_notes TEXT,
                bank_reconciled BOOLEAN NOT NULL DEFAULT FALSE,
                inventory_counted BOOLEAN NOT NULL DEFAULT FALSE,
                ar_reconciled BOOLEAN NOT NULL DEFAULT FALSE,
                ap_reconciled BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT uq_fiscal_periods_year_number UNIQUE (fiscal_year_id, period_number)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_fiscal_periods_entity ON fiscal_periods(entity_id)'))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_fiscal_periods_year ON fiscal_periods(fiscal_year_id)'))
        print('fiscal_periods table created')
        
        # Create journal_entries table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS journal_entries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE CASCADE,
                fiscal_period_id UUID REFERENCES fiscal_periods(id),
                entry_number VARCHAR(30) NOT NULL,
                entry_date DATE NOT NULL,
                description VARCHAR(500) NOT NULL,
                memo TEXT,
                entry_type journalentrytype NOT NULL DEFAULT 'MANUAL',
                source_module VARCHAR(50),
                source_document_type VARCHAR(50),
                source_document_id UUID,
                source_reference VARCHAR(100),
                total_debit NUMERIC(18, 2) NOT NULL,
                total_credit NUMERIC(18, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
                exchange_rate NUMERIC(18, 6) NOT NULL DEFAULT 1,
                status journalentrystatus NOT NULL DEFAULT 'DRAFT',
                requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
                approved_by_id UUID REFERENCES users(id),
                approved_at TIMESTAMP,
                posted_by_id UUID REFERENCES users(id),
                posted_at TIMESTAMP,
                is_reversed BOOLEAN NOT NULL DEFAULT FALSE,
                reversed_by_id UUID REFERENCES users(id),
                reversed_at TIMESTAMP,
                reversal_entry_id UUID,
                original_entry_id UUID,
                reversal_reason VARCHAR(500),
                reconciliation_id UUID,
                is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
                recurring_entry_id UUID,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                created_by_id UUID REFERENCES users(id),
                updated_by_id UUID REFERENCES users(id),
                CONSTRAINT uq_journal_entries_entity_number UNIQUE (entity_id, entry_number)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_journal_entries_entity ON journal_entries(entity_id)'))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_journal_entries_date ON journal_entries(entry_date)'))
        print('journal_entries table created')
        
        # Create journal_entry_lines table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS journal_entry_lines (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
                account_id UUID NOT NULL REFERENCES chart_of_accounts(id),
                line_number INTEGER NOT NULL,
                description VARCHAR(500),
                debit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
                credit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
                department_id UUID,
                project_id UUID,
                cost_center_id UUID,
                tax_code VARCHAR(20),
                tax_amount NUMERIC(18, 2),
                customer_id UUID,
                vendor_id UUID,
                bank_transaction_id UUID,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_entry ON journal_entry_lines(journal_entry_id)'))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_account ON journal_entry_lines(account_id)'))
        print('journal_entry_lines table created')
        
        # Create account_balances table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS account_balances (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id UUID NOT NULL REFERENCES chart_of_accounts(id) ON DELETE CASCADE,
                fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE,
                opening_balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
                period_debit NUMERIC(18, 2) NOT NULL DEFAULT 0,
                period_credit NUMERIC(18, 2) NOT NULL DEFAULT 0,
                closing_balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
                last_calculated_at TIMESTAMP,
                CONSTRAINT uq_account_balances_account_period UNIQUE (account_id, fiscal_period_id)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_account_balances_account ON account_balances(account_id)'))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_account_balances_period ON account_balances(fiscal_period_id)'))
        print('account_balances table created')
        
        # Create recurring_journal_entries table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS recurring_journal_entries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(500),
                template_data JSONB NOT NULL,
                frequency VARCHAR(20) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                next_run_date DATE,
                last_run_date DATE,
                run_count INTEGER NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                auto_post BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                created_by_id UUID REFERENCES users(id)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_recurring_journal_entries_entity ON recurring_journal_entries(entity_id)'))
        print('recurring_journal_entries table created')
        
        # Create gl_integration_logs table
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS gl_integration_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE CASCADE,
                source_module VARCHAR(50) NOT NULL,
                source_document_type VARCHAR(50) NOT NULL,
                source_document_id UUID NOT NULL,
                source_reference VARCHAR(100),
                journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
                is_reversed BOOLEAN NOT NULL DEFAULT FALSE,
                reversal_log_id UUID,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                posted_by_id UUID REFERENCES users(id),
                CONSTRAINT uq_gl_integration_source UNIQUE (entity_id, source_module, source_document_type, source_document_id)
            )
        '''))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_gl_integration_logs_entity ON gl_integration_logs(entity_id)'))
        await session.execute(text('CREATE INDEX IF NOT EXISTS ix_gl_integration_logs_source ON gl_integration_logs(source_module, source_document_type)'))
        print('gl_integration_logs table created')
        
        await session.commit()
        print('All accounting tables created successfully!')


if __name__ == "__main__":
    asyncio.run(create_accounting_tables())
