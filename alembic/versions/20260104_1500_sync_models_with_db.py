"""Add missing model columns and notifications table

Revision ID: 20260104_1500_sync_models_with_db
Revises: 20260104_1054
Create Date: 2026-01-04 15:00:00.000000

This migration syncs the database with all model definitions:
- transactions: wht_amount, wht_service_type, wht_payee_type
- invoices: is_b2c_reportable, b2c_reported_at, b2c_report_reference, b2c_report_deadline
- fixed_assets: department, assigned_to, warranty_expiry, notes, asset_metadata
- notifications: Create entire table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers
revision: str = '20260104_1500_sync_models_with_db'
down_revision: Union[str, None] = '20260104_1054'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Add missing columns and create notifications table."""
    
    # =====================================================
    # TRANSACTIONS TABLE - Add WHT tracking columns
    # =====================================================
    if not column_exists('transactions', 'wht_amount'):
        op.add_column('transactions', sa.Column(
            'wht_amount',
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default='0',
            comment='Withholding Tax amount in Naira'
        ))
    
    if not column_exists('transactions', 'wht_service_type'):
        op.add_column('transactions', sa.Column(
            'wht_service_type',
            sa.String(50),
            nullable=True,
            comment='Service type for WHT calculation (e.g., professional_services, consultancy)'
        ))
    
    if not column_exists('transactions', 'wht_payee_type'):
        op.add_column('transactions', sa.Column(
            'wht_payee_type',
            sa.String(20),
            nullable=True,
            comment='Payee type: individual or company'
        ))
    
    # =====================================================
    # INVOICES TABLE - Add B2C real-time reporting columns
    # =====================================================
    if not column_exists('invoices', 'is_b2c_reportable'):
        op.add_column('invoices', sa.Column(
            'is_b2c_reportable',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Whether invoice qualifies for B2C real-time NRS reporting'
        ))
    
    if not column_exists('invoices', 'b2c_reported_at'):
        op.add_column('invoices', sa.Column(
            'b2c_reported_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When B2C transaction was reported to NRS'
        ))
    
    if not column_exists('invoices', 'b2c_report_reference'):
        op.add_column('invoices', sa.Column(
            'b2c_report_reference',
            sa.String(100),
            nullable=True,
            comment='NRS reference for B2C report submission'
        ))
    
    if not column_exists('invoices', 'b2c_report_deadline'):
        op.add_column('invoices', sa.Column(
            'b2c_report_deadline',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='24-hour deadline for B2C NRS reporting'
        ))
    
    # =====================================================
    # FIXED ASSETS TABLE - Add tracking columns
    # =====================================================
    if not column_exists('fixed_assets', 'department'):
        op.add_column('fixed_assets', sa.Column(
            'department',
            sa.String(100),
            nullable=True,
            comment='Department that uses the asset'
        ))
    
    if not column_exists('fixed_assets', 'assigned_to'):
        op.add_column('fixed_assets', sa.Column(
            'assigned_to',
            sa.String(255),
            nullable=True,
            comment='Person or team assigned to the asset'
        ))
    
    if not column_exists('fixed_assets', 'warranty_expiry'):
        op.add_column('fixed_assets', sa.Column(
            'warranty_expiry',
            sa.Date(),
            nullable=True,
            comment='Warranty expiration date'
        ))
    
    if not column_exists('fixed_assets', 'notes'):
        op.add_column('fixed_assets', sa.Column(
            'notes',
            sa.Text(),
            nullable=True,
            comment='Additional notes about the asset'
        ))
    
    if not column_exists('fixed_assets', 'asset_metadata'):
        op.add_column('fixed_assets', sa.Column(
            'asset_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Additional asset metadata as JSON'
        ))
    
    # =====================================================
    # NOTIFICATIONS TABLE - Create new table
    # =====================================================
    if not table_exists('notifications'):
        # Create notification type enum
        op.execute("""
            CREATE TYPE notificationtype AS ENUM (
                'TAX_DEADLINE', 'VAT_REMINDER', 'PAYE_REMINDER', 'WHT_REMINDER', 
                'CIT_REMINDER', 'COMPLIANCE_WARNING',
                'INVOICE_CREATED', 'INVOICE_SENT', 'INVOICE_PAID', 
                'INVOICE_OVERDUE', 'INVOICE_DISPUTED',
                'NRS_SUBMISSION_SUCCESS', 'NRS_SUBMISSION_FAILED',
                'LOW_STOCK_ALERT', 'STOCK_WRITE_OFF',
                'SYSTEM_ANNOUNCEMENT', 'SECURITY_ALERT',
                'INFO', 'WARNING', 'ERROR', 'SUCCESS'
            )
        """)
        op.execute("CREATE TYPE notificationpriority AS ENUM ('LOW', 'NORMAL', 'HIGH', 'URGENT')")
        op.execute("CREATE TYPE notificationchannel AS ENUM ('IN_APP', 'EMAIL', 'SMS', 'PUSH')")
        
        op.create_table(
            'notifications',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('notification_type', sa.Enum(
                'TAX_DEADLINE', 'VAT_REMINDER', 'PAYE_REMINDER', 'WHT_REMINDER', 
                'CIT_REMINDER', 'COMPLIANCE_WARNING',
                'INVOICE_CREATED', 'INVOICE_SENT', 'INVOICE_PAID', 
                'INVOICE_OVERDUE', 'INVOICE_DISPUTED',
                'NRS_SUBMISSION_SUCCESS', 'NRS_SUBMISSION_FAILED',
                'LOW_STOCK_ALERT', 'STOCK_WRITE_OFF',
                'SYSTEM_ANNOUNCEMENT', 'SECURITY_ALERT',
                'INFO', 'WARNING', 'ERROR', 'SUCCESS',
                name='notificationtype', create_type=False
            ), nullable=False, server_default='INFO'),
            sa.Column('priority', sa.Enum(
                'LOW', 'NORMAL', 'HIGH', 'URGENT',
                name='notificationpriority', create_type=False
            ), nullable=False, server_default='NORMAL'),
            sa.Column('channels', postgresql.JSONB(astext_type=sa.Text()), nullable=False, 
                      server_default='["in_app"]', comment='List of delivery channels'),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('email_sent', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('email_sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('action_url', sa.String(500), nullable=True, comment='URL for notification action button'),
            sa.Column('action_label', sa.String(100), nullable=True, comment='Label for action button'),
            sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Additional notification data'),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='Notification expiry time'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['entity_id'], ['business_entities.id'], name=op.f('fk_notifications_entity_id_business_entities'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
        )
        
        # Create indexes
        op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
        op.create_index(op.f('ix_notifications_entity_id'), 'notifications', ['entity_id'], unique=False)
        op.create_index(op.f('ix_notifications_notification_type'), 'notifications', ['notification_type'], unique=False)
        op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
        op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)


def downgrade() -> None:
    """Remove added columns and notifications table."""
    
    # Drop notifications table
    if table_exists('notifications'):
        op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
        op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
        op.drop_index(op.f('ix_notifications_notification_type'), table_name='notifications')
        op.drop_index(op.f('ix_notifications_entity_id'), table_name='notifications')
        op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
        op.drop_table('notifications')
        
        # Drop enums
        op.execute("DROP TYPE IF EXISTS notificationchannel")
        op.execute("DROP TYPE IF EXISTS notificationpriority")
        op.execute("DROP TYPE IF EXISTS notificationtype")
    
    # Remove fixed_assets columns
    for col in ['department', 'assigned_to', 'warranty_expiry', 'notes', 'asset_metadata']:
        if column_exists('fixed_assets', col):
            op.drop_column('fixed_assets', col)
    
    # Remove invoices B2C columns
    for col in ['is_b2c_reportable', 'b2c_reported_at', 'b2c_report_reference', 'b2c_report_deadline']:
        if column_exists('invoices', col):
            op.drop_column('invoices', col)
    
    # Remove transactions WHT columns
    for col in ['wht_amount', 'wht_service_type', 'wht_payee_type']:
        if column_exists('transactions', col):
            op.drop_column('transactions', col)
