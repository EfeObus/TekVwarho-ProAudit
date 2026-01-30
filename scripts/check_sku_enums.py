"""Check SKU enum values in PostgreSQL vs Python"""
import asyncio
from sqlalchemy import text
from app.database import engine
from app.models.sku_enums import SKUTier, IntelligenceAddon, Feature

async def check_sku_tiers():
    print("=" * 60)
    print("SKU ENUM AUDIT")
    print("=" * 60)
    
    # Print Python enum values
    print("\n--- Python SKUTier Enum Values ---")
    for tier in SKUTier:
        print(f"  {tier.name} = '{tier.value}'")
    
    print("\n--- Python IntelligenceAddon Enum Values ---")
    for addon in IntelligenceAddon:
        print(f"  {addon.name} = '{addon.value}'")
    
    async with engine.begin() as conn:
        # Check PostgreSQL skutier enum
        print("\n--- PostgreSQL skutier Enum Values ---")
        result = await conn.execute(text("SELECT unnest(enum_range(NULL::skutier))"))
        rows = result.fetchall()
        for r in rows:
            print(f"  '{r[0]}'")
        
        # Check actual tenant_skus tier values
        print("\n--- Actual tenant_skus.tier Values ---")
        result = await conn.execute(text("SELECT DISTINCT tier, COUNT(*) FROM tenant_skus GROUP BY tier"))
        rows = result.fetchall()
        for r in rows:
            print(f"  tier='{r[0]}' count={r[1]}")
        
        # Check PostgreSQL intelligenceaddon enum
        print("\n--- PostgreSQL intelligenceaddon Enum Values ---")
        result = await conn.execute(text("SELECT unnest(enum_range(NULL::intelligenceaddon))"))
        rows = result.fetchall()
        for r in rows:
            print(f"  '{r[0]}'")
        
        # Check actual intelligence_addon values
        print("\n--- Actual tenant_skus.intelligence_addon Values ---")
        result = await conn.execute(text("SELECT DISTINCT intelligence_addon, COUNT(*) FROM tenant_skus GROUP BY intelligence_addon"))
        rows = result.fetchall()
        for r in rows:
            print(f"  intelligence_addon='{r[0]}' count={r[1]}")
        
        # Check a specific tenant's SKU
        print("\n--- Sample tenant_skus record ---")
        result = await conn.execute(text("""
            SELECT organization_id, tier, intelligence_addon, is_active 
            FROM tenant_skus 
            LIMIT 3
        """))
        rows = result.fetchall()
        for r in rows:
            print(f"  org={r[0]}, tier='{r[1]}', intel='{r[2]}', active={r[3]}")

if __name__ == "__main__":
    asyncio.run(check_sku_tiers())
