"""Add advanced audit system tables

Revision ID: 20260107_1800
Revises: 20260106_1600_advanced_accounting
Create Date: 2026-01-07 18:00:00.000000

Creates tables for:
- audit_runs: Reproducible audit execution records
- audit_findings: Human-readable audit findings
- audit_evidence: Immutable evidence storage
- auditor_sessions: Auditor access session tracking
- auditor_action_logs: Individual action logs

CRITICAL: All tables are append-only for immutability.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260107_1800_audit_system'
down_revision = '20260106_1600_advanced_accounting'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================
    # AUDIT RUNS TABLE
    # ===========================================
    op.create_table(
        'audit_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('run_type', sa.String(50), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending', index=True),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('rule_version', sa.String(50), nullable=False,
                  comment='Version of rules/algorithms used'),
        sa.Column('rule_config', postgresql.JSONB, nullable=False, default=dict,
                  comment='Configuration parameters for this run'),
        sa.Column('data_snapshot_id', sa.String(100), nullable=True,
                  comment='Reference to point-in-time data snapshot'),
        sa.Column('data_snapshot_hash', sa.String(64), nullable=True,
                  comment='SHA-256 hash of data snapshot'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_by', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='User who initiated the audit run'),
        sa.Column('total_records_analyzed', sa.Integer(), nullable=False, default=0),
        sa.Column('findings_count', sa.Integer(), nullable=False, default=0),
        sa.Column('critical_findings', sa.Integer(), default=0),
        sa.Column('high_findings', sa.Integer(), default=0),
        sa.Column('medium_findings', sa.Integer(), default=0),
        sa.Column('low_findings', sa.Integer(), default=0),
        sa.Column('result_summary', postgresql.JSONB, nullable=False, default=dict,
                  comment='Summary of audit results'),
        sa.Column('run_hash', sa.String(64), nullable=False,
                  comment='SHA-256 hash of run configuration and results'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    
    # Composite index for common queries
    op.create_index(
        'ix_audit_runs_entity_period',
        'audit_runs',
        ['entity_id', 'period_start', 'period_end']
    )
    
    # ===========================================
    # AUDIT FINDINGS TABLE
    # ===========================================
    op.create_table(
        'audit_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('audit_run_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('audit_runs.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('finding_ref', sa.String(50), nullable=False, unique=True,
                  comment='Human-readable finding reference (e.g., FIND-2026-00001)'),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('risk_level', sa.String(20), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False,
                  comment='Clear, concise title of the finding'),
        sa.Column('description', sa.Text(), nullable=False,
                  comment='Detailed description of what was found'),
        sa.Column('impact', sa.Text(), nullable=False,
                  comment='Business/compliance impact explanation'),
        sa.Column('affected_records', sa.Integer(), nullable=False, default=1,
                  comment='Number of records affected by this finding'),
        sa.Column('affected_amount', sa.Float(), nullable=True,
                  comment='Financial amount impacted (if applicable)'),
        sa.Column('affected_record_ids', postgresql.JSONB, nullable=False, default=list,
                  comment='List of affected record IDs'),
        sa.Column('evidence_summary', sa.Text(), nullable=False,
                  comment='Summary of supporting evidence'),
        sa.Column('evidence_ids', postgresql.JSONB, nullable=False, default=list,
                  comment='List of evidence record IDs'),
        sa.Column('recommendation', sa.Text(), nullable=False,
                  comment='Recommended corrective action'),
        sa.Column('regulatory_reference', sa.Text(), nullable=True,
                  comment='Relevant law/regulation reference (e.g., FITA 2023 s.45)'),
        sa.Column('detection_method', sa.String(100), nullable=False,
                  comment='Method used to detect this finding'),
        sa.Column('detection_details', postgresql.JSONB, nullable=False, default=dict,
                  comment='Technical details of detection'),
        sa.Column('confidence_score', sa.Float(), nullable=False, default=1.0,
                  comment='Confidence level 0.0-1.0'),
        sa.Column('is_false_positive', sa.Boolean(), nullable=False, default=False,
                  comment='Marked as false positive by reviewer'),
        sa.Column('false_positive_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finding_hash', sa.String(64), nullable=False,
                  comment='SHA-256 hash for immutability verification'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    
    # Composite index for risk-based queries
    op.create_index(
        'ix_audit_findings_entity_risk',
        'audit_findings',
        ['entity_id', 'risk_level']
    )
    
    # ===========================================
    # AUDIT EVIDENCE TABLE
    # ===========================================
    op.create_table(
        'audit_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('finding_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('audit_findings.id', ondelete='SET NULL'),
                  nullable=True, index=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('evidence_ref', sa.String(50), nullable=False, unique=True,
                  comment='Human-readable reference (e.g., EVID-2026-00001)'),
        sa.Column('evidence_type', sa.String(50), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('source_table', sa.String(100), nullable=True,
                  comment='Source table if from database'),
        sa.Column('source_record_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Source record ID if from database'),
        sa.Column('content', postgresql.JSONB, nullable=False, default=dict,
                  comment='Evidence content (JSON for structured data)'),
        sa.Column('file_path', sa.String(500), nullable=True,
                  comment='Path to attached file (WORM storage)'),
        sa.Column('file_mime_type', sa.String(100), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False,
                  comment='SHA-256 hash of content at creation time'),
        sa.Column('file_hash', sa.String(64), nullable=True,
                  comment='SHA-256 hash of attached file'),
        sa.Column('collected_by', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='User who collected/created this evidence'),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('collection_method', sa.String(100), nullable=False,
                  comment='How evidence was collected (automated/manual)'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    
    # Composite index for evidence queries
    op.create_index(
        'ix_audit_evidence_entity_type',
        'audit_evidence',
        ['entity_id', 'evidence_type']
    )
    
    # ===========================================
    # AUDITOR SESSIONS TABLE
    # ===========================================
    op.create_table(
        'auditor_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('auditor_user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('auditor_email', sa.String(255), nullable=False),
        sa.Column('auditor_name', sa.String(255), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('session_start', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('session_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('access_scope', postgresql.JSONB, nullable=False, default=dict,
                  comment='What the auditor is allowed to access'),
        sa.Column('actions_count', sa.Integer(), nullable=False, default=0),
        sa.Column('records_viewed', sa.Integer(), nullable=False, default=0),
        sa.Column('exports_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    
    # Composite index for active session queries
    op.create_index(
        'ix_auditor_sessions_entity_active',
        'auditor_sessions',
        ['entity_id', 'is_active']
    )
    
    # ===========================================
    # AUDITOR ACTION LOGS TABLE
    # ===========================================
    op.create_table(
        'auditor_action_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('auditor_sessions.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('resource_type', sa.String(100), nullable=False,
                  comment='Type of resource accessed (transaction, invoice, etc.)'),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='ID of specific resource accessed'),
        sa.Column('details', postgresql.JSONB, nullable=False, default=dict),
        sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('auditor_action_logs')
    op.drop_table('auditor_sessions')
    op.drop_table('audit_evidence')
    op.drop_table('audit_findings')
    op.drop_table('audit_runs')
