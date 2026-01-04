"""Add missing 2026 Tax Reform columns

Revision ID: 20260103_1700_add_missing_columns
Revises: 20260103_1630_ntaa_2025_compliance
Create Date: 2026-01-03 17:00:00.000000

This migration adds missing columns that should have been
applied in earlier migrations but were not:
- business_entities: business_type, annual_turnover, fixed_assets_value, 
  is_development_levy_exempt, b2c_realtime_reporting_enabled, b2c_reporting_threshold
- invoices: buyer_status, buyer_response_at, credit_note_id, is_credit_note, original_invoice_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers
revision = '20260103_1700_add_missing_columns'
down_revision = '20260103_1630_ntaa_2025_compliance'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add missing columns."""
    
    # =====================================================
    # BUSINESS ENTITY TABLE - Add 2026 Tax Reform columns
    # =====================================================
    if not column_exists('business_entities', 'business_type'):
        op.add_column('business_entities', sa.Column(
            'business_type',
            sa.Enum('BUSINESS_NAME', 'LIMITED_COMPANY', name='businesstype', create_type=False),
            nullable=False,
            server_default='LIMITED_COMPANY'
        ))
    
    if not column_exists('business_entities', 'annual_turnover'):
        op.add_column('business_entities', sa.Column(
            'annual_turnover',
            sa.Numeric(precision=15, scale=2),
            nullable=True
        ))
    
    if not column_exists('business_entities', 'fixed_assets_value'):
        op.add_column('business_entities', sa.Column(
            'fixed_assets_value',
            sa.Numeric(precision=15, scale=2),
            nullable=True
        ))
    
    if not column_exists('business_entities', 'is_development_levy_exempt'):
        op.add_column('business_entities', sa.Column(
            'is_development_levy_exempt',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))
    
    if not column_exists('business_entities', 'b2c_realtime_reporting_enabled'):
        op.add_column('business_entities', sa.Column(
            'b2c_realtime_reporting_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))
    
    if not column_exists('business_entities', 'b2c_reporting_threshold'):
        op.add_column('business_entities', sa.Column(
            'b2c_reporting_threshold',
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default='50000.00'
        ))
    
    # =====================================================
    # INVOICES TABLE - Add buyer review columns
    # =====================================================
    if not column_exists('invoices', 'buyer_status'):
        op.add_column('invoices', sa.Column(
            'buyer_status',
            sa.Enum('PENDING', 'ACCEPTED', 'REJECTED', name='buyerstatus', create_type=False),
            nullable=True,
            server_default='PENDING'
        ))
    
    if not column_exists('invoices', 'buyer_response_at'):
        op.add_column('invoices', sa.Column(
            'buyer_response_at',
            sa.DateTime(timezone=True),
            nullable=True
        ))
    
    if not column_exists('invoices', 'credit_note_id'):
        op.add_column('invoices', sa.Column(
            'credit_note_id',
            postgresql.UUID(as_uuid=True),
            nullable=True
        ))
    
    if not column_exists('invoices', 'is_credit_note'):
        op.add_column('invoices', sa.Column(
            'is_credit_note',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))
    
    if not column_exists('invoices', 'original_invoice_id'):
        op.add_column('invoices', sa.Column(
            'original_invoice_id',
            postgresql.UUID(as_uuid=True),
            nullable=True
        ))


def downgrade() -> None:
    """Remove added columns."""
    # Business entities columns
    for col in ['business_type', 'annual_turnover', 'fixed_assets_value', 
                'is_development_levy_exempt', 'b2c_realtime_reporting_enabled', 
                'b2c_reporting_threshold']:
        if column_exists('business_entities', col):
            op.drop_column('business_entities', col)
    
    # Invoice columns
    for col in ['buyer_status', 'buyer_response_at', 'credit_note_id', 
                'is_credit_note', 'original_invoice_id']:
        if column_exists('invoices', col):
            op.drop_column('invoices', col)
