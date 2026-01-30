#!/usr/bin/env python3
"""
Create all database tables on Railway using SQLAlchemy directly.
This bypasses Alembic migrations which have enum conflicts.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

# Import Base first
from app.models.base import BaseModel

# Import ALL models to register them with Base.metadata
# This ensures all tables are created
from app.models import (
    user,
    organization,
    entity,
    customer,
    vendor,
    transaction,
    invoice,
    inventory,
    notification,
    fixed_asset,
    sku,
    payroll,
    bank_reconciliation,
    advanced_accounting,
    tax_2026,
    audit_consolidated,
    report_template,
    category,
    accounting,
    emergency_control,
    expense_claims,
    legal_hold,
    ml_job,
    payroll_advanced,
    platform_api_key,
    risk_signal,
    support_ticket,
    tax,
    upsell,
)


def create_tables():
    """Create all tables in the database."""
    import os
    
    # Use DATABASE_URL from environment if available, otherwise use Railway default
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        "postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway"
    )
    
    print("=" * 60)
    print("TekVwarho ProAudit - Database Setup")
    print("=" * 60)
    
    # Create sync engine
    engine = create_engine(DATABASE_URL, echo=False)
    
    try:
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"\n✓ Connected to PostgreSQL: {version[:50]}...")
        
        # Drop all existing objects (clean slate)
        print("\n[1/4] Cleaning existing schema...")
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.commit()
        print("✓ Schema cleaned")
        
        # Create all tables
        print("\n[2/4] Creating tables from SQLAlchemy models...")
        BaseModel.metadata.create_all(bind=engine)
        print("✓ All tables created")
        
        # Verify tables were created
        print("\n[3/4] Verifying tables...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar()
            print(f"✓ {table_count} tables created")
            
            # List some key tables
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"\nTables: {', '.join(tables[:10])}{'...' if len(tables) > 10 else ''}")
        
        # Create alembic_version table and stamp to head
        print("\n[4/4] Setting up Alembic version tracking...")
        with engine.connect() as conn:
            # Create alembic_version table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))
            
            # Get the latest migration revision
            # We'll stamp it with a marker that indicates direct creation
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("""
                INSERT INTO alembic_version (version_num) 
                VALUES ('direct_create_20260130')
            """))
            conn.commit()
        print("✓ Alembic version table created and stamped")
        
        print("\n" + "=" * 60)
        print("✅ DATABASE SETUP COMPLETE!")
        print("=" * 60)
        print(f"\nRailway Database: turntable.proxy.rlwy.net:28165/railway")
        print(f"Tables created: {table_count}")
        print("\nNext steps:")
        print("1. Deploy your app to Railway")
        print("2. Set environment variables in Railway dashboard")
        print("3. Run seed scripts if needed")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)
