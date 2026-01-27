"""Add emergency controls for Super Admin

Revision ID: 20260126_2000
Revises: 20260126_1700
Create Date: 2026-01-26 20:00:00.000000

This migration adds emergency control features for Super Admins:
- emergency_controls: Audit log of all emergency actions
- platform_status: Current platform operational status
- Kill switches, read-only mode, maintenance mode support

CRITICAL SECURITY FEATURE
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260126_2000'
down_revision: Union[str, None] = '20260126_1700'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create emergency_action_type enum using raw SQL with IF NOT EXISTS
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE emergency_action_type AS ENUM (
                'read_only_mode',
                'maintenance_mode',
                'feature_kill_switch',
                'tenant_emergency_suspend',
                'user_emergency_suspend',
                'api_rate_limit_override',
                'login_lockdown'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create emergency_controls table
    op.execute("""
        CREATE TABLE IF NOT EXISTS emergency_controls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            action_type emergency_action_type NOT NULL,
            target_type VARCHAR(50) NOT NULL,
            target_id VARCHAR(255),
            initiated_by_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            reason TEXT NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            ended_at TIMESTAMP WITH TIME ZONE,
            ended_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            end_reason TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            affected_count INTEGER,
            action_metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Create indexes for emergency_controls
    op.execute("CREATE INDEX IF NOT EXISTS ix_emergency_controls_action_type ON emergency_controls(action_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_emergency_controls_is_active ON emergency_controls(is_active);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_emergency_controls_target ON emergency_controls(target_type, target_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_emergency_controls_started_at ON emergency_controls(started_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_emergency_controls_initiated_by ON emergency_controls(initiated_by_id);")
    
    # Create platform_status table (single-row table for quick lookups)
    op.execute("""
        CREATE TABLE IF NOT EXISTS platform_status (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            is_read_only BOOLEAN NOT NULL DEFAULT FALSE,
            is_maintenance_mode BOOLEAN NOT NULL DEFAULT FALSE,
            is_login_locked BOOLEAN NOT NULL DEFAULT FALSE,
            maintenance_message TEXT,
            maintenance_expected_end TIMESTAMP WITH TIME ZONE,
            disabled_features JSONB DEFAULT '[]'::jsonb,
            last_changed_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            last_changed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Insert initial platform status record if it doesn't exist
    op.execute("""
        INSERT INTO platform_status (
            id, is_read_only, is_maintenance_mode, is_login_locked, 
            disabled_features, created_at, updated_at
        )
        SELECT gen_random_uuid(), false, false, false, '[]'::jsonb, now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM platform_status);
    """)
    
    # Add is_emergency_suspended column to organizations table if it doesn't exist
    # Using raw SQL with IF NOT EXISTS pattern
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE organizations ADD COLUMN IF NOT EXISTS is_emergency_suspended BOOLEAN DEFAULT FALSE;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE organizations ADD COLUMN IF NOT EXISTS emergency_suspended_at TIMESTAMP WITH TIME ZONE;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE organizations ADD COLUMN IF NOT EXISTS emergency_suspended_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE organizations ADD COLUMN IF NOT EXISTS emergency_suspension_reason TEXT;
        END $$;
    """)
    
    # Create index for emergency suspended tenants
    op.execute("CREATE INDEX IF NOT EXISTS ix_organizations_emergency_suspended ON organizations(is_emergency_suspended);")


def downgrade() -> None:
    # Remove organizations columns
    op.drop_index('ix_organizations_emergency_suspended', table_name='organizations')
    op.drop_column('organizations', 'emergency_suspension_reason')
    op.drop_column('organizations', 'emergency_suspended_by_id')
    op.drop_column('organizations', 'emergency_suspended_at')
    op.drop_column('organizations', 'is_emergency_suspended')
    
    # Drop platform_status table
    op.drop_table('platform_status')
    
    # Drop emergency_controls indexes
    op.drop_index('ix_emergency_controls_initiated_by', table_name='emergency_controls')
    op.drop_index('ix_emergency_controls_started_at', table_name='emergency_controls')
    op.drop_index('ix_emergency_controls_target', table_name='emergency_controls')
    op.drop_index('ix_emergency_controls_is_active', table_name='emergency_controls')
    op.drop_index('ix_emergency_controls_action_type', table_name='emergency_controls')
    
    # Drop emergency_controls table
    op.drop_table('emergency_controls')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS emergency_action_type")
