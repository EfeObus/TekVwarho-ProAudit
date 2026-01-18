"""Add advanced payroll tables

Revision ID: 20260110_1000
Revises: 20260108_2030_add_bank_reconciliation_expense_claims
Create Date: 2026-01-10 10:00:00.000000

This migration creates advanced payroll tables:
- compliance_snapshots: Compliance status tracking
- payroll_impact_previews: Preview changes before committing
- payroll_exceptions: Exception flags with acknowledgement
- payroll_decision_logs: Immutable audit trail for payroll decisions
- ytd_payroll_ledgers: Year-to-date payroll tracking
- opening_balance_imports: Track imported opening balances
- payslip_explanations: Detailed payslip explanations
- employee_variance_logs: Track salary variances
- ctc_snapshots: Cost-to-company analytics
- what_if_simulations: What-if scenario analysis
- ghost_worker_detections: Ghost worker detection records
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


# revision identifiers, used by Alembic.
revision = '20260110_1000'
down_revision = '20260108_2030'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # ===========================================
    # COMPLIANCE SNAPSHOTS
    # ===========================================
    if not table_exists('compliance_snapshots'):
        op.create_table('compliance_snapshots',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('period_month', sa.Integer, nullable=False),
            sa.Column('period_year', sa.Integer, nullable=False),
            sa.Column('remittance_type', sa.String(30), nullable=False, comment='paye, pension, nhf, nsitf, itf'),
            sa.Column('status', sa.String(30), nullable=False, comment='on_time, overdue, partially_paid, penalty_risk, not_due, exempt'),
            sa.Column('amount_due', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('amount_paid', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('due_date', sa.Date, nullable=True),
            sa.Column('days_overdue', sa.Integer, default=0, nullable=False),
            sa.Column('estimated_penalty', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('penalty_calculation', JSONB, nullable=True, comment='Detailed penalty breakdown'),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('entity_id', 'period_month', 'period_year', 'remittance_type', name='uq_compliance_snapshot_entity_period_type'),
        )
    
    # ===========================================
    # PAYROLL IMPACT PREVIEWS
    # ===========================================
    if not table_exists('payroll_impact_previews'):
        op.create_table('payroll_impact_previews',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='CASCADE'), nullable=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=True),
            sa.Column('change_type', sa.String(50), nullable=False, comment='salary_change, allowance_change, new_hire, termination, etc'),
            sa.Column('field_changed', sa.String(100), nullable=True, comment='Specific field that changed'),
            sa.Column('old_value', sa.Numeric(18, 2), nullable=True),
            sa.Column('new_value', sa.Numeric(18, 2), nullable=True),
            sa.Column('impact_on_gross', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('impact_on_tax', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('impact_on_pension', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('impact_on_net', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('impact_details', JSONB, nullable=True, comment='Detailed breakdown of impact'),
            sa.Column('preview_generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('is_applied', sa.Boolean, default=False, nullable=False),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('applied_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # PAYROLL EXCEPTIONS
    # ===========================================
    if not table_exists('payroll_exceptions'):
        op.create_table('payroll_exceptions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='SET NULL'), nullable=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('exception_code', sa.String(50), nullable=False, comment='Standardized exception code'),
            sa.Column('severity', sa.String(20), nullable=False, comment='critical, warning, info'),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=False),
            sa.Column('expected_value', sa.String(255), nullable=True),
            sa.Column('actual_value', sa.String(255), nullable=True),
            sa.Column('recommendation', sa.Text, nullable=True),
            sa.Column('context_data', JSONB, nullable=True, comment='Additional context'),
            sa.Column('is_acknowledged', sa.Boolean, default=False, nullable=False),
            sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('acknowledged_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('acknowledgement_note', sa.Text, nullable=True),
            sa.Column('is_resolved', sa.Boolean, default=False, nullable=False),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolved_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('resolution_note', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            
            sa.Index('ix_payroll_exceptions_severity', 'severity'),
            sa.Index('ix_payroll_exceptions_code', 'exception_code'),
        )
    
    # ===========================================
    # PAYROLL DECISION LOGS (Immutable)
    # ===========================================
    if not table_exists('payroll_decision_logs'):
        op.create_table('payroll_decision_logs',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='SET NULL'), nullable=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True),
            sa.Column('decision_type', sa.String(50), nullable=False, comment='approval, adjustment, exception_override, note'),
            sa.Column('category', sa.String(50), nullable=False, comment='payroll, salary, deduction, exception, approval'),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=False),
            sa.Column('context_data', JSONB, nullable=False, default=dict, comment='Relevant context for the decision'),
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=False),
            sa.Column('created_by_name', sa.String(255), nullable=False),
            sa.Column('created_by_role', sa.String(100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('is_locked', sa.Boolean, default=False, nullable=False, comment='Locked after payroll completion'),
            sa.Column('content_hash', sa.String(64), nullable=True, comment='SHA-256 hash for integrity verification'),
            
            sa.Index('ix_payroll_decision_logs_type', 'decision_type'),
            sa.Index('ix_payroll_decision_logs_category', 'category'),
        )
    
    # ===========================================
    # YTD PAYROLL LEDGERS
    # ===========================================
    if not table_exists('ytd_payroll_ledgers'):
        op.create_table('ytd_payroll_ledgers',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('tax_year', sa.Integer, nullable=False),
            
            # YTD Earnings
            sa.Column('ytd_gross_salary', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_basic_salary', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_housing_allowance', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_transport_allowance', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_other_allowances', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_bonuses', sa.Numeric(18, 2), default=0, nullable=False),
            
            # YTD Deductions
            sa.Column('ytd_paye', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_employee_pension', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_employer_pension', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_nhf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_loans', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_other_deductions', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_net_pay', sa.Numeric(18, 2), default=0, nullable=False),
            
            # 2026 Tax Reform Fields
            sa.Column('ytd_consolidated_relief', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('ytd_rent_relief', sa.Numeric(18, 2), default=0, nullable=False),
            
            # Monthly Breakdown
            sa.Column('monthly_breakdown', JSONB, nullable=True, comment='Month-by-month details'),
            
            # Last Update
            sa.Column('last_payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('last_payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='SET NULL'), nullable=True),
            sa.Column('last_updated_month', sa.Integer, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('entity_id', 'employee_id', 'tax_year', name='uq_ytd_ledger_entity_employee_year'),
        )
    
    # ===========================================
    # OPENING BALANCE IMPORTS
    # ===========================================
    if not table_exists('opening_balance_imports'):
        op.create_table('opening_balance_imports',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('tax_year', sa.Integer, nullable=False),
            sa.Column('import_month', sa.Integer, nullable=False, comment='Month up to which balances are imported'),
            
            # Imported Balances
            sa.Column('gross_salary', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('basic_salary', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('paye', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('employee_pension', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('employer_pension', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('nhf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('net_pay', sa.Numeric(18, 2), default=0, nullable=False),
            
            # Source Info
            sa.Column('source_system', sa.String(100), nullable=True),
            sa.Column('source_reference', sa.String(255), nullable=True),
            sa.Column('import_notes', sa.Text, nullable=True),
            
            # Import Metadata
            sa.Column('imported_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('is_verified', sa.Boolean, default=False, nullable=False),
            sa.Column('verified_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
            
            sa.UniqueConstraint('entity_id', 'employee_id', 'tax_year', name='uq_opening_balance_entity_employee_year'),
        )
    
    # ===========================================
    # PAYSLIP EXPLANATIONS
    # ===========================================
    if not table_exists('payslip_explanations'):
        op.create_table('payslip_explanations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('section', sa.String(50), nullable=False, comment='earnings, deductions, taxes, net_pay'),
            sa.Column('item_name', sa.String(100), nullable=False),
            sa.Column('explanation', sa.Text, nullable=False),
            sa.Column('calculation_breakdown', JSONB, nullable=True),
            sa.Column('legal_reference', sa.String(255), nullable=True),
            sa.Column('sort_order', sa.Integer, default=0, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # EMPLOYEE VARIANCE LOGS
    # ===========================================
    if not table_exists('employee_variance_logs'):
        op.create_table('employee_variance_logs',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('payslip_id', UUID(as_uuid=True), sa.ForeignKey('payslips.id', ondelete='SET NULL'), nullable=True),
            
            # Variance Details
            sa.Column('field_name', sa.String(100), nullable=False),
            sa.Column('previous_value', sa.Numeric(18, 2), nullable=True),
            sa.Column('current_value', sa.Numeric(18, 2), nullable=True),
            sa.Column('variance_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('variance_percent', sa.Numeric(8, 2), nullable=True),
            sa.Column('variance_reason', sa.String(50), nullable=True, comment='new_hire, salary_increase, etc'),
            sa.Column('explanation', sa.Text, nullable=True),
            
            # Flags
            sa.Column('is_flagged', sa.Boolean, default=False, nullable=False),
            sa.Column('flag_severity', sa.String(20), nullable=True, comment='warning, critical'),
            sa.Column('is_reviewed', sa.Boolean, default=False, nullable=False),
            sa.Column('reviewed_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('review_note', sa.Text, nullable=True),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # CTC SNAPSHOTS (Cost-to-Company)
    # ===========================================
    if not table_exists('ctc_snapshots'):
        op.create_table('ctc_snapshots',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('payroll_run_id', UUID(as_uuid=True), sa.ForeignKey('payroll_runs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('period_month', sa.Integer, nullable=False),
            sa.Column('period_year', sa.Integer, nullable=False),
            
            # Cost Components
            sa.Column('gross_salary', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('employer_pension', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('employer_nhf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('employer_nsitf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('employer_itf', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('other_employer_costs', sa.Numeric(18, 2), default=0, nullable=False),
            sa.Column('total_ctc', sa.Numeric(18, 2), default=0, nullable=False),
            
            # Breakdown
            sa.Column('cost_breakdown', JSONB, nullable=True),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            
            sa.UniqueConstraint('entity_id', 'employee_id', 'period_month', 'period_year', name='uq_ctc_snapshot_entity_employee_period'),
        )
    
    # ===========================================
    # WHAT-IF SIMULATIONS
    # ===========================================
    if not table_exists('what_if_simulations'):
        op.create_table('what_if_simulations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            
            # Simulation Details
            sa.Column('simulation_name', sa.String(255), nullable=False),
            sa.Column('simulation_type', sa.String(50), nullable=False, comment='salary_change, allowance_change, mass_change, tax_scenario'),
            sa.Column('description', sa.Text, nullable=True),
            
            # Input Parameters
            sa.Column('input_parameters', JSONB, nullable=False),
            
            # Results
            sa.Column('baseline_results', JSONB, nullable=True, comment='Current state before changes'),
            sa.Column('simulated_results', JSONB, nullable=True, comment='Results after simulated changes'),
            sa.Column('comparison_summary', JSONB, nullable=True, comment='Side-by-side comparison'),
            
            # Status
            sa.Column('status', sa.String(30), default='draft', nullable=False, comment='draft, completed, applied'),
            sa.Column('is_applied', sa.Boolean, default=False, nullable=False),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('applied_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
    
    # ===========================================
    # GHOST WORKER DETECTIONS
    # ===========================================
    if not table_exists('ghost_worker_detections'):
        op.create_table('ghost_worker_detections',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('detection_run_id', sa.String(50), nullable=False, comment='Unique ID for the detection run'),
            
            # Detection Details
            sa.Column('detection_type', sa.String(50), nullable=False, comment='duplicate_bvn, duplicate_account, suspicious_pattern, etc'),
            sa.Column('risk_score', sa.Numeric(5, 2), nullable=False, comment='0-100 risk score'),
            sa.Column('risk_level', sa.String(20), nullable=False, comment='low, medium, high, critical'),
            
            # Evidence
            sa.Column('detection_details', JSONB, nullable=False, comment='Evidence and details'),
            sa.Column('related_employee_ids', JSONB, nullable=True, comment='IDs of related employees (for duplicates)'),
            
            # Resolution
            sa.Column('is_resolved', sa.Boolean, default=False, nullable=False),
            sa.Column('resolution_status', sa.String(30), nullable=True, comment='false_positive, confirmed, under_investigation'),
            sa.Column('resolved_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolution_notes', sa.Text, nullable=True),
            
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            
            sa.Index('ix_ghost_worker_risk_level', 'risk_level'),
            sa.Index('ix_ghost_worker_detection_type', 'detection_type'),
        )


def downgrade() -> None:
    op.drop_table('ghost_worker_detections')
    op.drop_table('what_if_simulations')
    op.drop_table('ctc_snapshots')
    op.drop_table('employee_variance_logs')
    op.drop_table('payslip_explanations')
    op.drop_table('opening_balance_imports')
    op.drop_table('ytd_payroll_ledgers')
    op.drop_table('payroll_decision_logs')
    op.drop_table('payroll_exceptions')
    op.drop_table('payroll_impact_previews')
    op.drop_table('compliance_snapshots')
