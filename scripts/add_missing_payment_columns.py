"""
Fix payment_transactions table - add missing columns

This script adds columns that exist in the SQLAlchemy model but are missing in the database.
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


async def add_missing_columns():
    """Add missing columns to payment_transactions table."""
    engine = create_async_engine(settings.database_url_async)
    
    # All columns that should exist based on the model
    columns_to_add = [
        ("paystack_fee_kobo", "BIGINT"),
        ("initiated_at", "TIMESTAMP DEFAULT NOW()"),
        ("completed_at", "TIMESTAMP"),
        ("expires_at", "TIMESTAMP"),
        ("bank_name", "VARCHAR(100)"),
        ("failure_reason", "VARCHAR(500)"),
        ("user_agent", "VARCHAR(500)"),
        ("refund_reference", "VARCHAR(100)"),
        ("refund_reason", "VARCHAR(500)"),
        ("paystack_invoice_id", "VARCHAR(100)"),
        ("paystack_invoice_status", "VARCHAR(50)"),
    ]
    
    async with engine.begin() as conn:
        print("Adding missing columns to payment_transactions...")
        
        for col_name, col_type in columns_to_add:
            try:
                await conn.execute(text(f"""
                    ALTER TABLE payment_transactions 
                    ADD COLUMN IF NOT EXISTS {col_name} {col_type}
                """))
                print(f"  ✓ Added/verified column: {col_name}")
            except Exception as e:
                print(f"  ✗ {col_name}: {e}")
        
        # List all columns to verify
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'payment_transactions'
            ORDER BY ordinal_position
        """))
        
        print(f"\nCurrent columns ({result.rowcount} total):")
        for row in result.fetchall():
            print(f"  - {row[0]}")
    
    await engine.dispose()
    print("\n✓ Schema update completed!")


if __name__ == "__main__":
    asyncio.run(add_missing_columns())
