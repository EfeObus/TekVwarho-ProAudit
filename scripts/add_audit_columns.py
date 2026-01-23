"""Script to add missing columns to audit_runs table."""
import asyncio
from sqlalchemy import text
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine


async def add_columns():
    """Add run_id, title, description columns to audit_runs table."""
    async with engine.begin() as conn:
        # Check if columns exist first
        result = await conn.execute(text('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'audit_runs' AND column_name IN ('run_id', 'title', 'description')
        '''))
        existing = [row[0] for row in result]
        print(f'Existing columns: {existing}')
        
        # Add run_id if not exists
        if 'run_id' not in existing:
            await conn.execute(text('ALTER TABLE audit_runs ADD COLUMN run_id VARCHAR(64)'))
            print('Added run_id column')
            
        # Add title if not exists  
        if 'title' not in existing:
            await conn.execute(text('ALTER TABLE audit_runs ADD COLUMN title VARCHAR(255)'))
            print('Added title column')
            
        # Add description if not exists
        if 'description' not in existing:
            await conn.execute(text('ALTER TABLE audit_runs ADD COLUMN description TEXT'))
            print('Added description column')
            
        # Create unique index on run_id if not exists
        try:
            await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_audit_runs_run_id ON audit_runs(run_id)'))
            print('Created unique index on run_id')
        except Exception as e:
            print(f'Index may already exist: {e}')
            
        print('Done!')


if __name__ == '__main__':
    asyncio.run(add_columns())
