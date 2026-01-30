"""
Test script to verify the billing subscription endpoint returns correct tier.
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def test_sku_data():
    from app.config import settings
    
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get Efe Obus org data
        result = await db.execute(text("""
            SELECT 
                o.id as org_id,
                o.name as org_name,
                o.subscription_tier as legacy_tier,
                ts.id as sku_id,
                ts.tier as sku_tier,
                ts.is_active,
                ts.billing_cycle,
                ts.current_period_start,
                ts.current_period_end
            FROM organizations o
            LEFT JOIN tenant_skus ts ON o.id = ts.organization_id
            WHERE o.name ILIKE '%efe obus%'
        """))
        row = result.fetchone()
        
        if row:
            print("=" * 60)
            print("DATABASE SKU STATE FOR EFE OBUS FURNITURE")
            print("=" * 60)
            print(f"Organization ID: {row[0]}")
            print(f"Organization Name: {row[1]}")
            print(f"Legacy subscription_tier: {row[2]}")
            print(f"TenantSKU ID: {row[3]}")
            print(f"TenantSKU tier: {row[4]}")
            print(f"TenantSKU is_active: {row[5]}")
            print(f"Billing Cycle: {row[6]}")
            print(f"Period Start: {row[7]}")
            print(f"Period End: {row[8]}")
            print("=" * 60)
            
            if row[4] and str(row[4]).lower() == 'enterprise':
                print("\n✅ SKU TIER IS ENTERPRISE - Menu access is CORRECT")
                print("❌ BUG: Settings page displays 'Core' instead of 'Enterprise'")
            
            # Test the billing service directly
            from app.services.billing_service import BillingService
            service = BillingService(db)
            info = await service.get_subscription_info(row[0])
            
            if info:
                print(f"\nBillingService.get_subscription_info() returns:")
                print(f"  - tier: {info.tier}")
                print(f"  - tier.value: {info.tier.value}")
                print(f"  - is_trial: {info.is_trial}")
                print(f"  - status: {info.status}")
            else:
                print("\n❌ BillingService.get_subscription_info() returned None!")
        else:
            print("Efe Obus org not found")

if __name__ == "__main__":
    asyncio.run(test_sku_data())
