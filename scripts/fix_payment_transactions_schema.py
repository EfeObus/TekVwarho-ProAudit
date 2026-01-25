"""
Fix payment_transactions table - convert enum columns to varchar

This script fixes the schema mismatch between the SQLAlchemy model (which expects varchar)
and the database (which has enum types for transaction_type and status columns).
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


async def fix_payment_transactions_schema():
    """Convert enum columns to varchar in payment_transactions table."""
    engine = create_async_engine(settings.database_url_async)
    
    async with engine.begin() as conn:
        print("Checking current column types...")
        
        # Check if columns are already varchar
        result = await conn.execute(text("""
            SELECT column_name, udt_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'payment_transactions'
            AND column_name IN ('transaction_type', 'status')
        """))
        rows = result.fetchall()
        
        for row in rows:
            print(f"  {row[0]}: {row[1]} ({row[2]})")
        
        needs_conversion = any(row[1] != 'varchar' for row in rows)
        
        if not needs_conversion:
            print("\n✓ Columns are already varchar, no conversion needed")
            await engine.dispose()
            return
        
        print("\nConverting enum columns to varchar...")
        
        try:
            # Convert transaction_type if it's an enum
            await conn.execute(text("""
                ALTER TABLE payment_transactions 
                ALTER COLUMN transaction_type TYPE VARCHAR(50)
                USING transaction_type::text
            """))
            print("  ✓ Converted transaction_type to VARCHAR(50)")
        except Exception as e:
            if "does not exist" in str(e).lower() or "type" in str(e).lower():
                print(f"  - transaction_type already correct or doesn't need conversion")
            else:
                print(f"  ✗ Error converting transaction_type: {e}")
        
        try:
            # Convert status if it's an enum
            await conn.execute(text("""
                ALTER TABLE payment_transactions 
                ALTER COLUMN status TYPE VARCHAR(50)
                USING status::text
            """))
            print("  ✓ Converted status to VARCHAR(50)")
        except Exception as e:
            if "does not exist" in str(e).lower() or "type" in str(e).lower():
                print(f"  - status already correct or doesn't need conversion")
            else:
                print(f"  ✗ Error converting status: {e}")
        
        # Verify the changes
        result = await conn.execute(text("""
            SELECT column_name, udt_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'payment_transactions'
            AND column_name IN ('transaction_type', 'status')
        """))
        
        print("\nFinal column types:")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]} ({row[2]})")
    
    await engine.dispose()
    print("\n✓ Schema fix completed!")


if __name__ == "__main__":
    asyncio.run(fix_payment_transactions_schema())
