"""Add payroll system tables

Revision ID: 20260106_1600
Revises: 20260106_1400_add_lga_email_verification
Create Date: 2026-01-06 16:00:00.000000

This migration creates the complete payroll system:
- employees: Employee records with Nigerian compliance fields
- employee_bank_accounts: Bank account details for salary payment
- payroll_runs: Payroll batch processing records
- payslips: Individual employee payslips
- payslip_items: Line items for earnings/deductions
- statutory_remittances: PAYE, Pension, NHF, NSITF, ITF tracking
- employee_loans: Loan and advance tracking with deduction schedules
- employee_leaves: Leave management with balance tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON
import uuid


# revision identifiers, used by Alembic.
revision = '20260106_1600'
down_revision = '20260106_1400_add_lga_email_verification'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # ===========================================
    # EMPLOYEES TABLE
    # ===========================================
    if not table_exists('employees'):
        op.create_table('employees',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            
            # Employee Identification
            sa.Column('employee_id', sa.String(50), nullable=False, comment='Internal employee ID/staff number'),
            sa.Column('title', sa.String(20), nullable=True),
            sa.Column('first_name', sa.String(100), nullable=False),
            sa.Column('middle_name', sa.String(100), nullable=True),
            sa.Column('last_name', sa.String(100), nullable=False),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('phone_number', sa.String(20), nullable=True),
            sa.Column('date_of_birth', sa.Date, nullable=True),
            sa.Column('gender', sa.String(20), nullable=True),
            sa.Column('marital_status', sa.String(20), nullable=True),
            
            # Address
            sa.Column('address', sa.Text, nullable=True),
            sa.Column('city', sa.String(100), nullable=True),
            sa.Column('state', sa.String(100), nullable=True),
            sa.Column('lga', sa.String(100), nullable=True),
            
            # Nigerian Identification & Compliance
            sa.Column('nin', sa.String(20), nullable=True, comment='National Identification Number'),
            sa.Column('bvn', sa.String(20), nullable=True, comment='Bank Verification Number'),
            sa.Column('tin', sa.String(20), nullable=True, comment='Tax Identification Number'),
            sa.Column('tax_state', sa.String(100), nullable=True, comment='State where PAYE is remitted'),
            
            # Pension
            sa.Column('pension_pin', sa.String(30), nullable=True, comment='RSA PIN'),
            sa.Column('pfa', sa.String(50), nullable=True, comment='Pension Fund Administrator'),
            sa.Column('pfa_other', sa.String(100), nullable=True),
            sa.Column('pension_start_date', sa.Date, nullable=True),
            sa.Column('is_pension_exempt', sa.Boolean, default=False, nullable=False),
            
            # NHF
            sa.Column('nhf_number', sa.String(30), nullable=True),
            sa.Column('is_nhf_exempt', sa.Boolean, default=False, nullable=False),
            
            # 2026 Tax Reform - Rent Relief
            sa.Column('annual_rent_paid', sa.Numeric(15, 2), default=0, nullable=False, comment='Annual rent for Rent Relief calculation'),
            sa.Column('has_life_insurance', sa.Boolean, default=False, nullable=False),
            sa.Column('monthly_insurance_premium', sa.Numeric(15, 2), default=0, nullable=False),
            
            # Employment Details
            sa.Column('employment_type', sa.String(30), default='full_time', nullable=False),
            sa.Column('employment_status', sa.String(30), default='active', nullable=False),
            sa.Column('department', sa.String(100), nullable=True),
            sa.Column('job_title', sa.String(150), nullable=True),
            sa.Column('job_grade', sa.String(50), nullable=True),
            sa.Column('hire_date', sa.Date, nullable=False),
            sa.Column('confirmation_date', sa.Date, nullable=True),
            sa.Column('termination_date', sa.Date, nullable=True),
            sa.Column('termination_reason', sa.Text, nullable=True),
            
            # Pay Structure
            sa.Column('payroll_frequency', sa.String(20), default='monthly', nullable=False),
            sa.Column('currency', sa.String(3), default='NGN', nullable=False),
            sa.Column('basic_salary', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('housing_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('transport_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('meal_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('utility_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('other_allowances', JSON, nullable=True),
            
            # Leave Entitlements
            sa.Column('annual_leave_days', sa.Integer, default=21, nullable=False),
            sa.Column('sick_leave_days', sa.Integer, default=12, nullable=False),
            sa.Column('leave_balance', sa.Numeric(5, 2), default=0, nullable=False),
            
            # Emergency Contact
            sa.Column('emergency_contact_name', sa.String(200), nullable=True),
            sa.Column('emergency_contact_phone', sa.String(20), nullable=True),
            sa.Column('emergency_contact_relationship', sa.String(50), nullable=True),
            
            # Next of Kin
            sa.Column('next_of_kin_name', sa.String(200), nullable=True),
            sa.Column('next_of_kin_phone', sa.String(20), nullable=True),
            sa.Column('next_of_kin_relationship', sa.String(50), nullable=True),
            sa.Column('next_of_kin_address', sa.Text, nullable=True),
            
            # Metadata
            sa.Column('is_active', sa.Boolean, default=True, nullable=False),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('updated_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('entity_id', 'employee_id', name='uq_employee_entity_id'),
        )
        # Note: entity_id index is auto-created by index=True in Column definition
    
    # ===========================================
    # EMPLOYEE BANK ACCOUNTS
    # ===========================================
    if not table_exists('employee_bank_accounts'):
        op.create_table('employee_bank_accounts',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('bank_name', sa.String(50), nullable=False),
            sa.Column('bank_name_other', sa.String(100), nullable=True),
            sa.Column('account_number', sa.String(20), nullable=False),
            sa.Column('account_name', sa.String(200), nullable=False),
            sa.Column('bank_code', sa.String(10), nullable=True, comment='CBN bank code'),
            sa.Column('is_primary', sa.Boolean, default=True, nullable=False),
            sa.Column('is_active', sa.Boolean, default=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # PAYROLL RUNS
    # ===========================================
    if not table_exists('payroll_runs'):
        op.create_table('payroll_runs',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_code', sa.String(50), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            
            # Pay Period
            sa.Column('frequency', sa.String(20), default='monthly', nullable=False),
            sa.Column('period_start', sa.Date, nullable=False),
            sa.Column('period_end', sa.Date, nullable=False),
            sa.Column('payment_date', sa.Date, nullable=False),
            
            # Status
            sa.Column('status', sa.String(30), default='draft', nullable=False),
            
            # Summary Totals
            sa.Column('total_employees', sa.Integer, default=0, nullable=False),
            sa.Column('total_gross_pay', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_deductions', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_net_pay', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_employer_contributions', sa.Numeric(18, 2), default=0, nullable=False),
            
            # Statutory Totals
            sa.Column('total_paye', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_pension_employee', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_pension_employer', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_nhf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_nsitf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_itf', sa.Numeric(18, 2), default=0, nullable=False),
            
            # Approval Workflow
            sa.Column('approved_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            
            # Audit Lock
            sa.Column('is_locked', sa.Boolean, default=False, nullable=False, comment='Locked for audit - immutable'),
            sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
            
            # Audit
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('updated_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('entity_id', 'payroll_code', name='uq_payroll_entity_code'),
        )
        # Note: entity_id index is auto-created by index=True in Column definition
    
    # ===========================================
    # PAYSLIPS
    # ===========================================
    if not table_exists('payslips'):
        op.create_table('payslips',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payslip_number', sa.String(50), nullable=False),
            
            # Days
            sa.Column('days_in_period', sa.Integer, default=30, nullable=False),
            sa.Column('days_worked', sa.Integer, default=30, nullable=False),
            sa.Column('days_absent', sa.Integer, default=0, nullable=False),
            
            # Earnings
            sa.Column('basic_salary', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('housing_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('transport_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('meal_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('utility_allowance', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('overtime_pay', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('bonus', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('other_earnings', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('gross_pay', sa.Numeric(15, 2), default=0, nullable=False),
            
            # Statutory Deductions
            sa.Column('paye_tax', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('pension_employee', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('nhf', sa.Numeric(15, 2), default=0, nullable=False),
            
            # Voluntary Deductions
            sa.Column('loan_deduction', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('salary_advance_deduction', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('cooperative_deduction', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('union_dues', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('other_deductions', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('total_deductions', sa.Numeric(15, 2), default=0, nullable=False),
            
            # Net Pay
            sa.Column('net_pay', sa.Numeric(15, 2), default=0, nullable=False),
            
            # Employer Contributions
            sa.Column('pension_employer', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('nsitf', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('itf', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('hmo_employer', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('group_life_insurance', sa.Numeric(15, 2), default=0, nullable=False),
            
            # 2026 Tax Relief Calculations
            sa.Column('consolidated_relief', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('rent_relief', sa.Numeric(15, 2), default=0, nullable=False, comment='20% of annual rent, max ₦500K'),
            sa.Column('pension_relief', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('nhf_relief', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('taxable_income', sa.Numeric(15, 2), default=0, nullable=False),
            
            # Detailed Breakdown (JSON)
            sa.Column('earnings_breakdown', JSON, nullable=True),
            sa.Column('deductions_breakdown', JSON, nullable=True),
            sa.Column('tax_calculation', JSON, nullable=True),
            
            # Bank Details
            sa.Column('bank_name', sa.String(100), nullable=True),
            sa.Column('account_number', sa.String(20), nullable=True),
            sa.Column('account_name', sa.String(200), nullable=True),
            
            # Payment Status
            sa.Column('is_paid', sa.Boolean, default=False, nullable=False),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('payment_reference', sa.String(100), nullable=True),
            
            # Notifications
            sa.Column('is_emailed', sa.Boolean, default=False, nullable=False),
            sa.Column('emailed_at', sa.DateTime(timezone=True), nullable=True),
            
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('payroll_run_id', 'employee_id', name='uq_payslip_run_employee'),
        )
    
    # ===========================================
    # PAYSLIP ITEMS (Line Items)
    # ===========================================
    if not table_exists('payslip_items'):
        op.create_table('payslip_items',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_type', sa.String(30), nullable=False, comment='earning, deduction, employer_contribution'),
            sa.Column('category', sa.String(50), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('amount', sa.Numeric(15, 2), nullable=False),
            sa.Column('is_percentage', sa.Boolean, default=False, nullable=False),
            sa.Column('percentage_value', sa.Numeric(5, 2), nullable=True),
            sa.Column('base_amount', sa.Numeric(15, 2), nullable=True),
            sa.Column('is_statutory', sa.Boolean, default=False, nullable=False),
            sa.Column('is_taxable', sa.Boolean, default=True, nullable=False),
            sa.Column('is_pensionable', sa.Boolean, default=False, nullable=False),
            sa.Column('sort_order', sa.Integer, default=0, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # STATUTORY REMITTANCES
    # ===========================================
    if not table_exists('statutory_remittances'):
        op.create_table('statutory_remittances',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('remittance_type', sa.String(50), nullable=False, comment='paye, pension, nhf, nsitf, itf'),
            sa.Column('period_month', sa.Integer, nullable=False),
            sa.Column('period_year', sa.Integer, nullable=False),
            sa.Column('amount_due', sa.Numeric(18, 2), nullable=False),
            sa.Column('amount_paid', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('due_date', sa.Date, nullable=False),
            sa.Column('is_paid', sa.Boolean, default=False, nullable=False),
            sa.Column('payment_date', sa.Date, nullable=True),
            sa.Column('payment_reference', sa.String(100), nullable=True),
            sa.Column('receipt_number', sa.String(100), nullable=True),
            sa.Column('receipt_file_path', sa.String(500), nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('updated_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('entity_id', 'remittance_type', 'period_month', 'period_year', name='uq_remittance_entity_type_period'),
        )
        # Note: entity_id index is auto-created by index=True in Column definition
    
    # ===========================================
    # EMPLOYEE LOANS & ADVANCES
    # ===========================================
    if not table_exists('employee_loans'):
        op.create_table('employee_loans',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('loan_type', sa.String(50), nullable=False, comment='loan, salary_advance, cooperative'),
            sa.Column('loan_reference', sa.String(50), nullable=False),
            sa.Column('description', sa.String(500), nullable=True),
            sa.Column('principal_amount', sa.Numeric(15, 2), nullable=False),
            sa.Column('interest_rate', sa.Numeric(5, 2), default=0, nullable=False, comment='Annual interest rate %'),
            sa.Column('total_amount', sa.Numeric(15, 2), nullable=False, comment='Principal + Interest'),
            sa.Column('monthly_deduction', sa.Numeric(15, 2), nullable=False),
            sa.Column('total_paid', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('balance', sa.Numeric(15, 2), nullable=False),
            sa.Column('tenure_months', sa.Integer, nullable=False),
            sa.Column('start_date', sa.Date, nullable=False),
            sa.Column('end_date', sa.Date, nullable=False),
            sa.Column('status', sa.String(30), default='active', nullable=False, comment='pending, active, completed, cancelled'),
            sa.Column('is_active', sa.Boolean, default=True, nullable=False),
            sa.Column('approved_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index('ix_employee_loans_status', 'employee_loans', ['status'])
    
    # ===========================================
    # LOAN REPAYMENTS
    # ===========================================
    if not table_exists('loan_repayments'):
        op.create_table('loan_repayments',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('loan_id', UUID(as_uuid=True), sa.ForeignKey('employee_loans.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='SET NULL'), nullable=True),
            sa.Column('repayment_date', sa.Date, nullable=False),
            sa.Column('amount', sa.Numeric(15, 2), nullable=False),
            sa.Column('principal_portion', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('interest_portion', sa.Numeric(15, 2), default=0, nullable=False),
            sa.Column('balance_after', sa.Numeric(15, 2), nullable=False),
            sa.Column('is_manual', sa.Boolean, default=False, nullable=False, comment='True if not deducted via payroll'),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # EMPLOYEE LEAVES
    # ===========================================
    if not table_exists('employee_leaves'):
        op.create_table('employee_leaves',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('leave_type', sa.String(50), nullable=False, comment='annual, sick, maternity, paternity, study, compassionate, unpaid'),
            sa.Column('start_date', sa.Date, nullable=False),
            sa.Column('end_date', sa.Date, nullable=False),
            sa.Column('days_requested', sa.Numeric(5, 2), nullable=False),
            sa.Column('days_approved', sa.Numeric(5, 2), nullable=True),
            sa.Column('reason', sa.Text, nullable=True),
            sa.Column('status', sa.String(30), default='pending', nullable=False, comment='pending, approved, rejected, cancelled'),
            sa.Column('is_paid', sa.Boolean, default=True, nullable=False, comment='Paid leave or unpaid'),
            sa.Column('reviewed_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('rejection_reason', sa.Text, nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index('ix_employee_leaves_status', 'employee_leaves', ['status'])
        op.create_index('ix_employee_leaves_dates', 'employee_leaves', ['start_date', 'end_date'])
    
    # ===========================================
    # PAYROLL SETTINGS (Per Entity)
    # ===========================================
    if not table_exists('payroll_settings'):
        op.create_table('payroll_settings',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, unique=True),
            
            # Company Info for Payslips
            sa.Column('company_name', sa.String(255), nullable=True),
            sa.Column('company_address', sa.Text, nullable=True),
            sa.Column('company_logo_path', sa.String(500), nullable=True),
            
            # Tax Settings
            sa.Column('tax_state', sa.String(100), nullable=True, comment='State for PAYE remittance'),
            sa.Column('tax_office', sa.String(255), nullable=True),
            sa.Column('employer_tin', sa.String(20), nullable=True),
            
            # Pension Settings
            sa.Column('pfa_name', sa.String(100), nullable=True, comment='Default PFA for new employees'),
            sa.Column('pension_employee_rate', sa.Numeric(5, 2), default=8, nullable=False),
            sa.Column('pension_employer_rate', sa.Numeric(5, 2), default=10, nullable=False),
            
            # NHF Settings
            sa.Column('nhf_rate', sa.Numeric(5, 2), default=2.5, nullable=False),
            
            # NSITF/ITF Settings
            sa.Column('nsitf_rate', sa.Numeric(5, 2), default=1, nullable=False),
            sa.Column('itf_rate', sa.Numeric(5, 2), default=1, nullable=False),
            sa.Column('itf_applicable', sa.Boolean, default=False, nullable=False, comment='True if 5+ employees'),
            
            # Payment Settings
            sa.Column('default_payment_day', sa.Integer, default=25, nullable=False),
            sa.Column('prorate_new_employees', sa.Boolean, default=True, nullable=False),
            
            # Approval Workflow
            sa.Column('require_approval', sa.Boolean, default=True, nullable=False),
            sa.Column('auto_lock_after_days', sa.Integer, default=30, nullable=False, comment='Days after which payroll is locked'),
            
            # Payslip Settings
            sa.Column('payslip_template', sa.String(50), default='standard', nullable=False),
            sa.Column('email_payslips', sa.Boolean, default=True, nullable=False),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table('payroll_settings')
    op.drop_table('employee_leaves')
    op.drop_table('loan_repayments')
    op.drop_table('employee_loans')
    op.drop_table('statutory_remittances')
    op.drop_table('payslip_items')
    op.drop_table('payslips')
    op.drop_table('payroll_runs')
    op.drop_table('employee_bank_accounts')
    op.drop_table('employees')
