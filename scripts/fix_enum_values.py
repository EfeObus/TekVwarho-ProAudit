"""
Fix missing PostgreSQL enum values for feature and usagemetrictype.
"""
import asyncio
from sqlalchemy import text
from app.database import engine as async_engine

# Missing feature enum values
MISSING_FEATURES = [
    'BENFORDS_LAW',
    'WORM_VAULT',
    'FORENSIC_AUDIT',
    'AUDIT_INTELLIGENCE',
    'MULTI_CURRENCY',
    'FX_MANAGEMENT',
    'CONSOLIDATION',
    'BUDGET_MANAGEMENT',
    'ADVANCED_REPORTING',
    'CUSTOM_REPORTS',
    'API_ACCESS',
    'WEBHOOKS',
    'SSO',
    'AUDIT_TRAIL',
    'DATA_EXPORT',
    'COMPLIANCE_REPORTS',
    'TAX_REPORTS',
    'PAYROLL',
    'INVENTORY',
    'FIXED_ASSETS',
]

# Missing usagemetrictype enum values
MISSING_METRICS = [
    'API_CALLS',
    'STORAGE_BYTES',
    'TRANSACTIONS',
    'USERS',
    'ENTITIES',
    'REPORTS',
    'EXPORTS',
    'IMPORTS',
    'WEBHOOKS',
    'INTEGRATIONS',
]

async def fix_enums():
    async with async_engine.begin() as conn:
        # Get existing feature enum values
        result = await conn.execute(text("""
            SELECT enumlabel FROM pg_enum 
            WHERE enumtypid = 'feature'::regtype
            ORDER BY enumsortorder;
        """))
        existing_features = [row[0] for row in result.fetchall()]
        print(f"Existing feature values: {existing_features}")
        
        # Add missing feature values
        for feature in MISSING_FEATURES:
            if feature not in existing_features:
                try:
                    await conn.execute(text(f"ALTER TYPE feature ADD VALUE IF NOT EXISTS '{feature}';"))
                    print(f"  Added feature: {feature}")
                except Exception as e:
                    print(f"  Skipped feature {feature}: {e}")
        
        # Get existing usagemetrictype enum values
        result = await conn.execute(text("""
            SELECT enumlabel FROM pg_enum 
            WHERE enumtypid = 'usagemetrictype'::regtype
            ORDER BY enumsortorder;
        """))
        existing_metrics = [row[0] for row in result.fetchall()]
        print(f"\nExisting usagemetrictype values: {existing_metrics}")
        
        # Add missing usagemetrictype values
        for metric in MISSING_METRICS:
            if metric not in existing_metrics:
                try:
                    await conn.execute(text(f"ALTER TYPE usagemetrictype ADD VALUE IF NOT EXISTS '{metric}';"))
                    print(f"  Added usagemetrictype: {metric}")
                except Exception as e:
                    print(f"  Skipped usagemetrictype {metric}: {e}")
        
        print("\n✅ Enum values updated successfully!")

if __name__ == "__main__":
    asyncio.run(fix_enums())
