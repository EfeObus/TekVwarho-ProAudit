"""Add IAS 21 currency translation fields to consolidation models

Revision ID: 20260127_1000
Revises: 20260127_0900_fx_fields
Create Date: 2026-01-27 10:00:00.000000

This migration adds:
1. Currency translation fields to entity_group_members
2. New currency_translation_history table for tracking translations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '20260127_1000'
down_revision = '20260127_0900_fx_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================
    # ADD TRANSLATION FIELDS TO ENTITY_GROUP_MEMBERS
    # ===========================================
    
    # Add functional_currency column
    op.add_column('entity_group_members', 
        sa.Column('functional_currency', sa.String(3), nullable=True, 
            comment="Entity's functional currency")
    )
    
    # Add cumulative_translation_adjustment column
    op.add_column('entity_group_members',
        sa.Column('cumulative_translation_adjustment', sa.Numeric(18, 2), 
            nullable=True, default=0,
            comment="CTA - goes to OCI (Other Comprehensive Income)")
    )
    
    # Add last_translation_date column
    op.add_column('entity_group_members',
        sa.Column('last_translation_date', sa.Date, nullable=True,
            comment="Date of most recent translation")
    )
    
    # Add last_translation_rate column
    op.add_column('entity_group_members',
        sa.Column('last_translation_rate', sa.Numeric(18, 6), nullable=True,
            comment="Closing rate used in last translation")
    )
    
    # Add average_rate_period column
    op.add_column('entity_group_members',
        sa.Column('average_rate_period', sa.Numeric(18, 6), nullable=True,
            comment="Average rate for income statement translation")
    )
    
    # Add translation_method column
    op.add_column('entity_group_members',
        sa.Column('translation_method', sa.String(20), nullable=True, default='current_rate',
            comment="IAS 21 translation method: current_rate or temporal")
    )
    
    # Add historical_equity_rate column
    op.add_column('entity_group_members',
        sa.Column('historical_equity_rate', sa.Numeric(18, 6), nullable=True,
            comment="Historical rate for translating equity opening balances")
    )
    
    # Set default functional_currency to NGN for existing records
    op.execute("UPDATE entity_group_members SET functional_currency = 'NGN' WHERE functional_currency IS NULL")
    op.execute("UPDATE entity_group_members SET translation_method = 'current_rate' WHERE translation_method IS NULL")
    op.execute("UPDATE entity_group_members SET cumulative_translation_adjustment = 0 WHERE cumulative_translation_adjustment IS NULL")
    
    # ===========================================
    # CREATE CURRENCY_TRANSLATION_HISTORY TABLE
    # ===========================================
    
    op.create_table(
        'currency_translation_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        
        # Foreign keys
        sa.Column('group_id', UUID(as_uuid=True), sa.ForeignKey('entity_groups.id'), nullable=False),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('entity_group_members.id'), nullable=False),
        sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('business_entities.id'), nullable=False),
        sa.Column('fiscal_period_id', UUID(as_uuid=True), sa.ForeignKey('fiscal_periods.id'), nullable=True),
        
        # Period information
        sa.Column('translation_date', sa.Date, nullable=False),
        
        # Currency pair
        sa.Column('functional_currency', sa.String(3), nullable=False, comment="Subsidiary's functional currency"),
        sa.Column('presentation_currency', sa.String(3), nullable=False, comment="Group's presentation currency"),
        
        # Exchange rates used
        sa.Column('closing_rate', sa.Numeric(18, 6), nullable=False, comment="Rate at balance sheet date"),
        sa.Column('average_rate', sa.Numeric(18, 6), nullable=False, comment="Average rate for income statement"),
        sa.Column('historical_equity_rate', sa.Numeric(18, 6), nullable=True, comment="Historical rate for equity"),
        
        # Pre-translation amounts (in functional currency)
        sa.Column('pre_translation_assets', sa.Numeric(18, 2), default=0),
        sa.Column('pre_translation_liabilities', sa.Numeric(18, 2), default=0),
        sa.Column('pre_translation_equity', sa.Numeric(18, 2), default=0),
        sa.Column('pre_translation_revenue', sa.Numeric(18, 2), default=0),
        sa.Column('pre_translation_expenses', sa.Numeric(18, 2), default=0),
        sa.Column('pre_translation_net_income', sa.Numeric(18, 2), default=0),
        
        # Post-translation amounts (in presentation currency)
        sa.Column('post_translation_assets', sa.Numeric(18, 2), default=0),
        sa.Column('post_translation_liabilities', sa.Numeric(18, 2), default=0),
        sa.Column('post_translation_equity', sa.Numeric(18, 2), default=0),
        sa.Column('post_translation_revenue', sa.Numeric(18, 2), default=0),
        sa.Column('post_translation_expenses', sa.Numeric(18, 2), default=0),
        sa.Column('post_translation_net_income', sa.Numeric(18, 2), default=0),
        
        # Translation adjustments
        sa.Column('translation_adjustment', sa.Numeric(18, 2), default=0,
            comment="Current period translation difference"),
        sa.Column('cumulative_translation_adjustment', sa.Numeric(18, 2), default=0,
            comment="Running total CTA balance"),
        
        # Metadata
        sa.Column('translation_method', sa.String(20), default='current_rate'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    
    # Create indexes
    op.create_index('ix_translation_group_period', 'currency_translation_history', 
        ['group_id', 'translation_date'])
    op.create_index('ix_translation_entity', 'currency_translation_history', 
        ['entity_id', 'translation_date'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_translation_entity', table_name='currency_translation_history')
    op.drop_index('ix_translation_group_period', table_name='currency_translation_history')
    
    # Drop table
    op.drop_table('currency_translation_history')
    
    # Remove columns from entity_group_members
    op.drop_column('entity_group_members', 'historical_equity_rate')
    op.drop_column('entity_group_members', 'translation_method')
    op.drop_column('entity_group_members', 'average_rate_period')
    op.drop_column('entity_group_members', 'last_translation_rate')
    op.drop_column('entity_group_members', 'last_translation_date')
    op.drop_column('entity_group_members', 'cumulative_translation_adjustment')
    op.drop_column('entity_group_members', 'functional_currency')
