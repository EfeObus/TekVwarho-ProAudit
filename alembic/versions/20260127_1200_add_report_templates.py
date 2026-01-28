"""Add report template tables

Revision ID: 20260127_1200
Revises: 20260127_1100
Create Date: 2026-01-27 12:00:00.000000

This migration adds tables for customizable report templates:
- report_templates: Template configuration with branding, formatting, layout
- report_template_sections: Section configuration within templates
- report_generation_logs: Audit trail for report generation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260127_1200'
down_revision = '20260127_1100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # REPORT TEMPLATES TABLE
    # ==========================================================================
    op.create_table(
        'report_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Ownership
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True,
                  comment='For organization-wide templates shared across entities'),
        
        # Template basics
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False, index=True,
                  comment='Type of report this template applies to'),
        sa.Column('is_default', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_system', sa.Boolean, default=False, comment='System templates cannot be deleted'),
        
        # Branding
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), default='#1a365d', comment='Hex color code for headers'),
        sa.Column('secondary_color', sa.String(7), default='#4a5568', comment='Hex color code for subheaders'),
        sa.Column('accent_color', sa.String(7), default='#38a169', comment='Hex color code for highlights'),
        sa.Column('negative_color', sa.String(7), default='#e53e3e', comment='Hex color code for negative values'),
        
        # Page settings
        sa.Column('page_size', sa.String(10), default='A4'),
        sa.Column('orientation', sa.String(15), default='portrait'),
        sa.Column('margin_top', sa.Float, default=20.0, comment='mm'),
        sa.Column('margin_bottom', sa.Float, default=20.0, comment='mm'),
        sa.Column('margin_left', sa.Float, default=15.0, comment='mm'),
        sa.Column('margin_right', sa.Float, default=15.0, comment='mm'),
        
        # Header/Footer
        sa.Column('header_text', sa.Text, nullable=True),
        sa.Column('footer_text', sa.Text, nullable=True, comment='Supports placeholders: {page}, {total_pages}, {date}, {company}'),
        sa.Column('show_page_numbers', sa.Boolean, default=True),
        sa.Column('show_report_date', sa.Boolean, default=True),
        sa.Column('show_prepared_by', sa.Boolean, default=True),
        sa.Column('show_company_info', sa.Boolean, default=True),
        
        # Typography
        sa.Column('title_font_size', sa.Integer, default=18),
        sa.Column('header_font_size', sa.Integer, default=12),
        sa.Column('body_font_size', sa.Integer, default=10),
        sa.Column('font_family', sa.String(50), default='Helvetica'),
        
        # Number formatting
        sa.Column('decimal_places', sa.Integer, default=2),
        sa.Column('thousand_separator', sa.String(1), default=','),
        sa.Column('decimal_separator', sa.String(1), default='.'),
        sa.Column('currency_symbol', sa.String(10), default='₦'),
        sa.Column('currency_position', sa.String(10), default='before', comment='before or after'),
        sa.Column('show_currency_symbol', sa.Boolean, default=True),
        sa.Column('show_zero_as_dash', sa.Boolean, default=False),
        sa.Column('parentheses_for_negative', sa.Boolean, default=True),
        
        # Column configuration (JSON)
        sa.Column('column_config', postgresql.JSONB, nullable=True,
                  comment='JSON config for column order, visibility, widths'),
        
        # Conditional formatting rules
        sa.Column('format_rules', postgresql.JSONB, nullable=True,
                  comment='JSON config for conditional formatting'),
        
        # Grouping/Sorting
        sa.Column('default_grouping', sa.String(50), nullable=True, comment='Default grouping field'),
        sa.Column('default_sort_field', sa.String(50), nullable=True),
        sa.Column('default_sort_direction', sa.String(4), default='asc', comment='asc or desc'),
        
        # Comparative options
        sa.Column('show_comparative', sa.Boolean, default=True),
        sa.Column('comparative_label', sa.String(50), default='Prior Period'),
        sa.Column('show_variance', sa.Boolean, default=True),
        sa.Column('show_variance_percent', sa.Boolean, default=True),
        
        # Subtotal options
        sa.Column('show_subtotals', sa.Boolean, default=True),
        sa.Column('show_grand_total', sa.Boolean, default=True),
        sa.Column('subtotal_style', sa.String(20), default='bold', comment='bold, italic, underline, highlight'),
        
        # Additional options
        sa.Column('custom_options', postgresql.JSONB, nullable=True, comment='Additional custom options'),
        
        # Multi-language
        sa.Column('language_code', sa.String(5), default='en'),
        sa.Column('translations', postgresql.JSONB, nullable=True, comment='Label translations for different languages'),
        
        # Usage tracking
        sa.Column('use_count', sa.Integer, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for report_templates
    op.create_index('ix_report_templates_entity_type', 'report_templates', ['entity_id', 'report_type'])
    op.create_index('ix_report_templates_entity_default', 'report_templates', ['entity_id', 'is_default'])
    
    # ==========================================================================
    # REPORT TEMPLATE SECTIONS TABLE
    # ==========================================================================
    op.create_table(
        'report_template_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('report_templates.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Section identity
        sa.Column('section_key', sa.String(50), nullable=False,
                  comment='e.g., assets, liabilities, revenue, expenses'),
        sa.Column('section_title', sa.String(100), nullable=False),
        sa.Column('section_order', sa.Integer, default=0),
        sa.Column('is_visible', sa.Boolean, default=True),
        
        # Section styling
        sa.Column('include_header', sa.Boolean, default=True),
        sa.Column('header_background', sa.String(7), nullable=True),
        sa.Column('indent_level', sa.Integer, default=0),
        
        # Subtotals
        sa.Column('show_section_total', sa.Boolean, default=True),
        sa.Column('total_label', sa.String(100), default='Total'),
        
        # Column overrides (JSON)
        sa.Column('column_overrides', postgresql.JSONB, nullable=True,
                  comment='Section-specific column configuration'),
        
        # Filter criteria
        sa.Column('filter_criteria', postgresql.JSONB, nullable=True,
                  comment='Filter accounts/items for this section'),
    )
    
    # Index for section ordering
    op.create_index('ix_report_template_sections_order', 'report_template_sections', 
                    ['template_id', 'section_order'])
    
    # ==========================================================================
    # REPORT GENERATION LOGS TABLE
    # ==========================================================================
    op.create_table(
        'report_generation_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        
        # Who/What
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('business_entities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('report_templates.id', ondelete='SET NULL'), nullable=True),
        
        # Report info
        sa.Column('report_type', sa.String(50), nullable=False, index=True),
        sa.Column('report_format', sa.String(10), nullable=False),
        
        # Report parameters
        sa.Column('report_params', postgresql.JSONB, nullable=True,
                  comment='Parameters used to generate the report'),
        
        # Timing
        sa.Column('generation_started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('generation_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('generation_time_ms', sa.Integer, nullable=True),
        
        # Result
        sa.Column('success', sa.Boolean, default=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('file_size_bytes', sa.Integer, nullable=True),
        sa.Column('row_count', sa.Integer, nullable=True),
        
        # Download tracking
        sa.Column('download_count', sa.Integer, default=0),
        sa.Column('last_downloaded_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Index for history queries
    op.create_index('ix_report_generation_logs_entity_date', 'report_generation_logs',
                    ['entity_id', 'generation_started_at'])
    op.create_index('ix_report_generation_logs_type_date', 'report_generation_logs',
                    ['report_type', 'generation_started_at'])


def downgrade() -> None:
    op.drop_table('report_generation_logs')
    op.drop_table('report_template_sections')
    op.drop_table('report_templates')
