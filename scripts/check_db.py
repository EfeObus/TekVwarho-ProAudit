"""Quick script to check database state for debugging."""
import asyncio
from app.database import async_session_maker
from sqlalchemy import text


async def check_database():
    print("Checking database state...")
    async with async_session_maker() as db:
        # Check entity for payroll runs
        result = await db.execute(text("SELECT DISTINCT entity_id FROM payroll_runs LIMIT 1"))
        row = result.fetchone()
        if row:
            print(f'Payroll entity_id: {row[0]}')
        
        # Check business entities table
        result = await db.execute(text("SELECT id, name FROM business_entities LIMIT 5"))
        rows = result.fetchall()
        print(f"\nBusiness Entities ({len(rows)} found):")
        for row in rows:
            print(f'  ID: {row[0]}, Name: {row[1]}')
        
        # Check compliance snapshots (correct table name)
        result = await db.execute(text("SELECT COUNT(*) FROM compliance_snapshots"))
        count = result.scalar()
        print(f'\nCompliance snapshots: {count}')
        
        # Check YTD data (correct table name)
        result = await db.execute(text("SELECT COUNT(*) FROM ytd_payroll_ledgers"))
        count = result.scalar()
        print(f'YTD payroll ledgers: {count}')
        
        # Check decision logs (correct table name)
        result = await db.execute(text("SELECT COUNT(*) FROM payroll_decision_logs"))
        count = result.scalar()
        print(f'Payroll decision logs: {count}')
        
        # Check payroll exceptions
        result = await db.execute(text("SELECT COUNT(*) FROM payroll_exceptions"))
        count = result.scalar()
        print(f'Payroll exceptions: {count}')
        
        # Check statutory remittances
        result = await db.execute(text("SELECT COUNT(*) FROM statutory_remittances"))
        count = result.scalar()
        print(f'Statutory remittances: {count}')


if __name__ == "__main__":
    asyncio.run(check_database())
