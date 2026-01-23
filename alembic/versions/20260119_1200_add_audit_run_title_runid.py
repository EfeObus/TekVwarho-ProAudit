"""Add run_id, title, and description to audit_runs table

Revision ID: 20260119_1200
Revises: 20260118_1200
Create Date: 2026-01-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260119_1200'
down_revision = '20260118_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add run_id, title, and description columns to audit_runs table."""
    
    # Check if audit_runs table exists
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'audit_runs' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('audit_runs')]
        
        # Add run_id column if not exists
        if 'run_id' not in existing_columns:
            op.add_column('audit_runs', sa.Column(
                'run_id', 
                sa.String(50), 
                nullable=True
            ))
            
            # Generate run_id for existing rows
            op.execute("""
                UPDATE audit_runs 
                SET run_id = 'AUD-' || TO_CHAR(created_at, 'YYYYMMDDHH24MISS') || '-' || UPPER(SUBSTRING(id::text, 1, 6))
                WHERE run_id IS NULL
            """)
            
            # Make run_id not nullable
            op.alter_column('audit_runs', 'run_id', nullable=False)
            
            # Add unique constraint and index
            op.create_index('ix_audit_runs_run_id', 'audit_runs', ['run_id'], unique=True)
        
        # Add title column if not exists
        if 'title' not in existing_columns:
            op.add_column('audit_runs', sa.Column(
                'title', 
                sa.String(200), 
                nullable=True
            ))
            
            # Generate title for existing rows
            op.execute("""
                UPDATE audit_runs 
                SET title = INITCAP(REPLACE(run_type, '_', ' ')) || ' - ' || TO_CHAR(period_start, 'YYYY-MM-DD')
                WHERE title IS NULL
            """)
            
            # Make title not nullable
            op.alter_column('audit_runs', 'title', nullable=False)
        
        # Add description column if not exists
        if 'description' not in existing_columns:
            op.add_column('audit_runs', sa.Column(
                'description', 
                sa.Text(), 
                nullable=True
            ))


def downgrade() -> None:
    """Remove run_id, title, and description columns from audit_runs table."""
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'audit_runs' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('audit_runs')]
        
        if 'run_id' in existing_columns:
            op.drop_index('ix_audit_runs_run_id', table_name='audit_runs')
            op.drop_column('audit_runs', 'run_id')
        
        if 'title' in existing_columns:
            op.drop_column('audit_runs', 'title')
        
        if 'description' in existing_columns:
            op.drop_column('audit_runs', 'description')
