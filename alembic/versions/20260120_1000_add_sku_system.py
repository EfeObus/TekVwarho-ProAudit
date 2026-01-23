"""Add SKU (Stock Keeping Unit) system for commercial product tiers

Revision ID: 20260120_1000
Revises: 20260119_1804_merge_audit_run_and_coa
Create Date: 2026-01-20 10:00:00.000000

This migration adds:
- sku_pricing: Pricing configuration for each SKU tier (CORE, PROFESSIONAL, ENTERPRISE)
- tenant_skus: SKU assignment for each organization (tenant)
- usage_records: Usage metrics tracking per organization per billing period
- usage_events: Individual usage events for real-time metering
- feature_access_logs: Log of feature access attempts for auditing

Nigerian Naira (NGN) pricing:
- CORE: ₦25,000 - ₦75,000/month
- PROFESSIONAL: ₦150,000 - ₦400,000/month
- ENTERPRISE: ₦1,000,000 - ₦5,000,000+/month
- Intelligence Add-on: ₦250,000 - ₦1,000,000/month
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '20260120_1000'
down_revision = 'dcc3fe505b58'
branch_labels = None
depends_on = None


# Define ENUMs
sku_tier_enum = postgresql.ENUM(
    'core', 'professional', 'enterprise',
    name='skutier',
    create_type=False
)

intelligence_addon_enum = postgresql.ENUM(
    'none', 'standard', 'advanced',
    name='intelligenceaddon',
    create_type=False
)

usage_metric_type_enum = postgresql.ENUM(
    'transactions', 'users', 'entities', 'invoices', 
    'api_calls', 'ocr_pages', 'storage_mb', 'ml_inferences', 'employees',
    name='usagemetrictype',
    create_type=False
)

feature_enum = postgresql.ENUM(
    # Core features
    'gl_enabled', 'chart_of_accounts', 'journal_entries', 'basic_reports',
    'tax_engine_basic', 'customer_management', 'vendor_management', 
    'basic_invoicing', 'audit_logs_standard', 'inventory_basic',
    # Professional features
    'payroll', 'payroll_advanced', 'bank_reconciliation', 'fixed_assets',
    'expense_claims', 'e_invoicing', 'nrs_compliance', 'advanced_reports',
    'rule_based_alerts', 'multi_user_rbac', 'inventory_advanced', 'dashboard_advanced',
    # Enterprise features
    'worm_vault', 'intercompany', 'multi_entity', 'attestation',
    'digital_signatures', 'sox_compliance', 'ifrs_compliance', 'frcn_compliance',
    'segregation_of_duties', 'full_api_access', 'priority_support', 
    'audit_vault_extended', 'consolidation',
    # Intelligence add-on features
    'ml_anomaly_detection', 'benfords_law', 'zscore_analysis',
    'predictive_forecasting', 'nlp_processing', 'ocr_extraction',
    'fraud_detection', 'custom_ml_training', 'behavioral_analytics',
    name='feature',
    create_type=False
)


def upgrade() -> None:
    # Create ENUM types first
    sku_tier_enum.create(op.get_bind(), checkfirst=True)
    intelligence_addon_enum.create(op.get_bind(), checkfirst=True)
    usage_metric_type_enum.create(op.get_bind(), checkfirst=True)
    feature_enum.create(op.get_bind(), checkfirst=True)
    
    # ==========================================================================
    # SKU Pricing table
    # ==========================================================================
    op.create_table(
        'sku_pricing',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # SKU tier
        sa.Column('sku_tier', sku_tier_enum, nullable=False, index=True),
        
        # Base pricing (Naira)
        sa.Column('base_price_monthly', sa.Numeric(12, 2), nullable=False, 
                  comment='Base monthly price in Naira'),
        sa.Column('base_price_annual', sa.Numeric(12, 2), nullable=False,
                  comment='Annual price in Naira (typically 15% discount)'),
        
        # Per-user pricing
        sa.Column('price_per_user', sa.Numeric(10, 2), nullable=True,
                  comment='Price per additional user in Naira'),
        
        # Intelligence add-on pricing
        sa.Column('intelligence_standard_price', sa.Numeric(12, 2), nullable=True,
                  comment='Standard Intelligence add-on price in Naira'),
        sa.Column('intelligence_advanced_price', sa.Numeric(12, 2), nullable=True,
                  comment='Advanced Intelligence add-on price in Naira'),
        
        # Effective dates
        sa.Column('effective_from', sa.Date, nullable=False),
        sa.Column('effective_to', sa.Date, nullable=True),
        
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('currency', sa.String(3), default='NGN', comment='ISO currency code'),
    )
    
    # ==========================================================================
    # Tenant SKUs table - SKU assignment per organization
    # ==========================================================================
    op.create_table(
        'tenant_skus',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Organization relationship
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'),
                  nullable=False, unique=True, index=True),
        
        # Current SKU tier
        sa.Column('tier', sku_tier_enum, default='core', nullable=False),
        
        # Intelligence add-on
        sa.Column('intelligence_addon', intelligence_addon_enum, default='none', nullable=True),
        
        # Billing cycle
        sa.Column('billing_cycle', sa.String(20), default='monthly', nullable=False),
        
        # Current billing period
        sa.Column('current_period_start', sa.Date, nullable=True),
        sa.Column('current_period_end', sa.Date, nullable=True),
        
        # Trial period
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When the trial period ends (null if not on trial)'),
        
        # Feature overrides (JSON)
        sa.Column('feature_overrides', postgresql.JSONB, nullable=True,
                  comment='Override specific features for this tenant'),
        
        # Custom limits (JSON)
        sa.Column('custom_limits', postgresql.JSONB, nullable=True,
                  comment='Custom usage limits for this tenant'),
        
        # Custom pricing (for enterprise deals)
        sa.Column('custom_price_naira', sa.Integer, nullable=True,
                  comment='Custom negotiated monthly price in Nigerian Naira'),
        
        # Status
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suspension_reason', sa.String(500), nullable=True),
        
        # Upgrade audit trail
        sa.Column('upgraded_from', sa.String(50), nullable=True,
                  comment='Previous tier before upgrade'),
        sa.Column('upgraded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('upgraded_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Custom limit overrides
        sa.Column('custom_user_limit', sa.Integer, nullable=True,
                  comment='Override default user limit for this tenant'),
        sa.Column('custom_entity_limit', sa.Integer, nullable=True,
                  comment='Override default entity limit for this tenant'),
        sa.Column('custom_transaction_limit', sa.Integer, nullable=True,
                  comment='Override default transaction limit (-1 for unlimited)'),
        
        # Notes
        sa.Column('notes', sa.Text, nullable=True),
    )
    
    # ==========================================================================
    # Usage Records table - Usage tracking per billing period
    # ==========================================================================
    op.create_table(
        'usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Organization relationship
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        
        # Period
        sa.Column('period_start', sa.Date, nullable=False),
        sa.Column('period_end', sa.Date, nullable=False),
        
        # Usage counts
        sa.Column('transactions_count', sa.BigInteger, default=0),
        sa.Column('users_count', sa.Integer, default=0),
        sa.Column('entities_count', sa.Integer, default=0),
        sa.Column('invoices_count', sa.Integer, default=0),
        sa.Column('api_calls_count', sa.BigInteger, default=0),
        sa.Column('ocr_pages_count', sa.Integer, default=0),
        sa.Column('storage_used_mb', sa.Numeric(10, 2), default=0),
        sa.Column('ml_inferences_count', sa.BigInteger, default=0),
        sa.Column('employees_count', sa.Integer, default=0),
        
        # Limit breach tracking
        sa.Column('limit_breaches', postgresql.JSONB, nullable=True,
                  comment='Record of any limit breaches this period'),
        
        # Billing
        sa.Column('is_billed', sa.Boolean, default=False),
        sa.Column('billed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invoice_reference', sa.String(100), nullable=True),
    )
    
    # Create index for efficient period lookups
    op.create_index(
        'ix_usage_records_org_period',
        'usage_records',
        ['organization_id', 'period_start', 'period_end']
    )
    
    # ==========================================================================
    # Usage Events table - Individual usage events for real-time metering
    # ==========================================================================
    op.create_table(
        'usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Organization relationship
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        
        # Optional entity and user
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Metric details
        sa.Column('metric_type', usage_metric_type_enum, nullable=False, index=True),
        sa.Column('quantity', sa.Integer, default=1),
        
        # Resource tracking
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        
        # Event metadata
        sa.Column('event_metadata', postgresql.JSONB, nullable=True),
    )
    
    # Create index for time-based aggregation
    op.create_index(
        'ix_usage_events_org_metric_created',
        'usage_events',
        ['organization_id', 'metric_type', 'created_at']
    )
    
    # ==========================================================================
    # Feature Access Logs table - Audit trail for feature access
    # ==========================================================================
    op.create_table(
        'feature_access_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Organization and user
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        
        # Feature access
        sa.Column('feature', feature_enum, nullable=False, index=True),
        sa.Column('was_granted', sa.Boolean, nullable=False),
        
        # Denial info
        sa.Column('denial_reason', sa.String(200), nullable=True),
        
        # Request context
        sa.Column('endpoint', sa.String(200), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
    )
    
    # Create index for feature access analytics
    op.create_index(
        'ix_feature_access_logs_org_feature_created',
        'feature_access_logs',
        ['organization_id', 'feature', 'created_at']
    )
    
    # ==========================================================================
    # Seed initial SKU pricing data (Nigerian Naira)
    # ==========================================================================
    op.execute("""
        INSERT INTO sku_pricing (
            id, sku_tier, base_price_monthly, base_price_annual, price_per_user,
            intelligence_standard_price, intelligence_advanced_price,
            effective_from, is_active, currency
        ) VALUES 
        -- CORE tier: ₦50,000/month, ₦510,000/year (15% discount)
        (
            gen_random_uuid(), 'core', 50000.00, 510000.00, 5000.00,
            NULL, NULL,
            '2026-01-01', true, 'NGN'
        ),
        -- PROFESSIONAL tier: ₦250,000/month, ₦2,550,000/year
        (
            gen_random_uuid(), 'professional', 250000.00, 2550000.00, 10000.00,
            350000.00, 750000.00,
            '2026-01-01', true, 'NGN'
        ),
        -- ENTERPRISE tier: ₦2,000,000/month, ₦20,400,000/year
        (
            gen_random_uuid(), 'enterprise', 2000000.00, 20400000.00, NULL,
            500000.00, 1000000.00,
            '2026-01-01', true, 'NGN'
        )
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_feature_access_logs_org_feature_created')
    op.drop_table('feature_access_logs')
    
    op.drop_index('ix_usage_events_org_metric_created')
    op.drop_table('usage_events')
    
    op.drop_index('ix_usage_records_org_period')
    op.drop_table('usage_records')
    
    op.drop_table('tenant_skus')
    op.drop_table('sku_pricing')
    
    # Drop ENUM types
    feature_enum.drop(op.get_bind(), checkfirst=True)
    usage_metric_type_enum.drop(op.get_bind(), checkfirst=True)
    intelligence_addon_enum.drop(op.get_bind(), checkfirst=True)
    sku_tier_enum.drop(op.get_bind(), checkfirst=True)
