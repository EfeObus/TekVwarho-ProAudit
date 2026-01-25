"""Add super admin dashboard models

Revision ID: 20260125_1800
Revises: 20260124_0900
Create Date: 2026-01-25 18:00:00.000000

This migration adds the following new tables for the Super Admin Dashboard:
- legal_holds: Legal hold records for compliance
- legal_hold_notifications: Notifications sent for legal holds
- risk_signals: Platform risk monitoring signals
- risk_signal_comments: Comments on risk signals
- ml_jobs: Machine learning job tracking
- ml_models: ML model registry
- upsell_opportunities: Revenue expansion opportunities
- upsell_activities: Activity tracking for upsell opportunities
- support_tickets: Support ticket system
- ticket_comments: Comments on support tickets
- ticket_attachments: File attachments for tickets
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260125_1800'
down_revision: Union[str, None] = '20260124_0900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create legal_holds table
    op.create_table('legal_holds',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('hold_number', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('matter_name', sa.String(length=255), nullable=False),
        sa.Column('matter_reference', sa.String(length=100), nullable=True),
        sa.Column('hold_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('data_scope', sa.String(length=50), nullable=False),
        sa.Column('preservation_start_date', sa.Date(), nullable=False),
        sa.Column('preservation_end_date', sa.Date(), nullable=True),
        sa.Column('hold_start_date', sa.DateTime(), nullable=True),
        sa.Column('hold_end_date', sa.DateTime(), nullable=True),
        sa.Column('legal_counsel_name', sa.String(length=255), nullable=True),
        sa.Column('legal_counsel_email', sa.String(length=255), nullable=True),
        sa.Column('legal_counsel_phone', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('entity_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('records_preserved_count', sa.Integer(), nullable=True),
        sa.Column('created_by_staff_id', sa.UUID(), nullable=True),
        sa.Column('released_by_staff_id', sa.UUID(), nullable=True),
        sa.Column('release_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_staff_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['released_by_staff_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_legal_holds_hold_number', 'legal_holds', ['hold_number'], unique=True)
    op.create_index('ix_legal_holds_organization', 'legal_holds', ['organization_id'])
    op.create_index('ix_legal_holds_status', 'legal_holds', ['status'])
    
    # Create legal_hold_notifications table
    op.create_table('legal_hold_notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('legal_hold_id', sa.UUID(), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_name', sa.String(length=255), nullable=True),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['legal_hold_id'], ['legal_holds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_legal_hold_notifications_hold', 'legal_hold_notifications', ['legal_hold_id'])
    
    # Create risk_signals table
    op.create_table('risk_signals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('signal_code', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('signal_type', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('auto_detected', sa.Boolean(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=True),
        sa.Column('detected_by_id', sa.UUID(), nullable=True),
        sa.Column('ml_model_id', sa.UUID(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recommended_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by_id', sa.UUID(), nullable=True),
        sa.Column('assigned_to_id', sa.UUID(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.UUID(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('requires_immediate_action', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['detected_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['acknowledged_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_signals_code', 'risk_signals', ['signal_code'], unique=True)
    op.create_index('ix_risk_signals_organization', 'risk_signals', ['organization_id'])
    op.create_index('ix_risk_signals_severity', 'risk_signals', ['severity'])
    op.create_index('ix_risk_signals_status', 'risk_signals', ['status'])
    
    # Create risk_signal_comments table
    op.create_table('risk_signal_comments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('risk_signal_id', sa.UUID(), nullable=False),
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['risk_signal_id'], ['risk_signals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_signal_comments_signal', 'risk_signal_comments', ['risk_signal_id'])
    
    # Create ml_models table (before ml_jobs since ml_jobs references it)
    op.create_table('ml_models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_name', sa.String(length=255), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('model_type', sa.String(length=50), nullable=False),
        sa.Column('algorithm', sa.String(length=100), nullable=False),
        sa.Column('framework', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('precision_score', sa.Float(), nullable=True),
        sa.Column('recall_score', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.Column('hyperparameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feature_names', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('training_samples_count', sa.Integer(), nullable=True),
        sa.Column('model_path', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_models_name', 'ml_models', ['model_name'])
    op.create_index('ix_ml_models_type', 'ml_models', ['model_type'])
    op.create_index('ix_ml_models_active', 'ml_models', ['is_active'])
    
    # Create ml_jobs table
    op.create_table('ml_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.String(length=100), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=True),
        sa.Column('model_id', sa.UUID(), nullable=True),
        sa.Column('target_organization_id', sa.UUID(), nullable=True),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_time_seconds', sa.Integer(), nullable=True),
        sa.Column('progress_percent', sa.Integer(), nullable=True),
        sa.Column('current_step', sa.String(length=255), nullable=True),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_files', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_jobs_job_id', 'ml_jobs', ['job_id'], unique=True)
    op.create_index('ix_ml_jobs_status', 'ml_jobs', ['status'])
    op.create_index('ix_ml_jobs_type', 'ml_jobs', ['job_type'])
    
    # Create upsell_opportunities table
    op.create_table('upsell_opportunities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('opportunity_code', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('upsell_type', sa.String(length=50), nullable=False),
        sa.Column('signal', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('estimated_mrr_increase', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('estimated_arr_increase', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('actual_mrr_increase', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('actual_arr_increase', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('current_product', sa.String(length=100), nullable=True),
        sa.Column('target_product', sa.String(length=100), nullable=True),
        sa.Column('assigned_to_id', sa.UUID(), nullable=True),
        sa.Column('signal_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('auto_detected', sa.Boolean(), nullable=True),
        sa.Column('identified_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('lost_reason', sa.Text(), nullable=True),
        sa.Column('next_action', sa.String(length=500), nullable=True),
        sa.Column('next_action_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_upsell_opportunities_code', 'upsell_opportunities', ['opportunity_code'], unique=True)
    op.create_index('ix_upsell_opportunities_organization', 'upsell_opportunities', ['organization_id'])
    op.create_index('ix_upsell_opportunities_status', 'upsell_opportunities', ['status'])
    
    # Create upsell_activities table
    op.create_table('upsell_activities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('upsell_opportunity_id', sa.UUID(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('performed_by_id', sa.UUID(), nullable=True),
        sa.Column('next_action', sa.String(length=500), nullable=True),
        sa.Column('next_action_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['upsell_opportunity_id'], ['upsell_opportunities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_upsell_activities_opportunity', 'upsell_activities', ['upsell_opportunity_id'])
    
    # Create support_tickets table
    op.create_table('support_tickets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket_number', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('reporter_user_id', sa.UUID(), nullable=True),
        sa.Column('reporter_email', sa.String(length=255), nullable=True),
        sa.Column('reporter_name', sa.String(length=255), nullable=True),
        sa.Column('assigned_to_id', sa.UUID(), nullable=True),
        sa.Column('resolved_by_id', sa.UUID(), nullable=True),
        sa.Column('sla_due_at', sa.DateTime(), nullable=True),
        sa.Column('sla_breached', sa.Boolean(), nullable=True),
        sa.Column('is_escalated', sa.Boolean(), nullable=True),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('escalation_level', sa.Integer(), nullable=True),
        sa.Column('first_response_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('response_time_minutes', sa.Integer(), nullable=True),
        sa.Column('resolution_time_minutes', sa.Integer(), nullable=True),
        sa.Column('satisfaction_rating', sa.Integer(), nullable=True),
        sa.Column('satisfaction_feedback', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reporter_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_support_tickets_number', 'support_tickets', ['ticket_number'], unique=True)
    op.create_index('ix_support_tickets_organization', 'support_tickets', ['organization_id'])
    op.create_index('ix_support_tickets_status', 'support_tickets', ['status'])
    op.create_index('ix_support_tickets_priority', 'support_tickets', ['priority'])
    
    # Create ticket_comments table
    op.create_table('ticket_comments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('support_ticket_id', sa.UUID(), nullable=False),
        sa.Column('staff_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('is_internal', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['support_ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ticket_comments_ticket', 'ticket_comments', ['support_ticket_id'])
    
    # Create ticket_attachments table
    op.create_table('ticket_attachments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('support_ticket_id', sa.UUID(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('uploaded_by_staff_id', sa.UUID(), nullable=True),
        sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['support_ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by_staff_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ticket_attachments_ticket', 'ticket_attachments', ['support_ticket_id'])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_index('ix_ticket_attachments_ticket', table_name='ticket_attachments')
    op.drop_table('ticket_attachments')
    
    op.drop_index('ix_ticket_comments_ticket', table_name='ticket_comments')
    op.drop_table('ticket_comments')
    
    op.drop_index('ix_support_tickets_priority', table_name='support_tickets')
    op.drop_index('ix_support_tickets_status', table_name='support_tickets')
    op.drop_index('ix_support_tickets_organization', table_name='support_tickets')
    op.drop_index('ix_support_tickets_number', table_name='support_tickets')
    op.drop_table('support_tickets')
    
    op.drop_index('ix_upsell_activities_opportunity', table_name='upsell_activities')
    op.drop_table('upsell_activities')
    
    op.drop_index('ix_upsell_opportunities_status', table_name='upsell_opportunities')
    op.drop_index('ix_upsell_opportunities_organization', table_name='upsell_opportunities')
    op.drop_index('ix_upsell_opportunities_code', table_name='upsell_opportunities')
    op.drop_table('upsell_opportunities')
    
    op.drop_index('ix_ml_jobs_type', table_name='ml_jobs')
    op.drop_index('ix_ml_jobs_status', table_name='ml_jobs')
    op.drop_index('ix_ml_jobs_job_id', table_name='ml_jobs')
    op.drop_table('ml_jobs')
    
    op.drop_index('ix_ml_models_active', table_name='ml_models')
    op.drop_index('ix_ml_models_type', table_name='ml_models')
    op.drop_index('ix_ml_models_name', table_name='ml_models')
    op.drop_table('ml_models')
    
    op.drop_index('ix_risk_signal_comments_signal', table_name='risk_signal_comments')
    op.drop_table('risk_signal_comments')
    
    op.drop_index('ix_risk_signals_status', table_name='risk_signals')
    op.drop_index('ix_risk_signals_severity', table_name='risk_signals')
    op.drop_index('ix_risk_signals_organization', table_name='risk_signals')
    op.drop_index('ix_risk_signals_code', table_name='risk_signals')
    op.drop_table('risk_signals')
    
    op.drop_index('ix_legal_hold_notifications_hold', table_name='legal_hold_notifications')
    op.drop_table('legal_hold_notifications')
    
    op.drop_index('ix_legal_holds_status', table_name='legal_holds')
    op.drop_index('ix_legal_holds_organization', table_name='legal_holds')
    op.drop_index('ix_legal_holds_hold_number', table_name='legal_holds')
    op.drop_table('legal_holds')
