"""
Script to create or update tenant SKU for an organization.
This enables access to all features including forensic audit (Benford's Law, WORM Vault, etc.)
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def create_or_update_sku():
    async with engine.begin() as conn:
        # Get the organization ID first
        result = await conn.execute(text("""
            SELECT organization_id FROM users WHERE email = 'efeobukohwo64@gmail.com'
        """))
        row = result.fetchone()
        if not row:
            print('User not found')
            return
        
        org_id = row[0]
        print(f'Organization ID: {org_id}')
        
        # Check if SKU already exists
        result = await conn.execute(text("""
            SELECT id, tier, intelligence_addon, is_active FROM tenant_skus WHERE organization_id = :org_id
        """), {"org_id": org_id})
        existing = result.fetchone()
        
        if existing:
            print(f'Existing SKU: id={existing[0]}, tier={existing[1]}, intelligence_addon={existing[2]}, is_active={existing[3]}')
            # Update to enterprise tier with intelligence addon
            await conn.execute(text("""
                UPDATE tenant_skus 
                SET tier = 'enterprise', intelligence_addon = 'advanced', is_active = true
                WHERE organization_id = :org_id
            """), {"org_id": org_id})
            print('Updated SKU to enterprise with advanced intelligence addon')
        else:
            # Insert new SKU with enterprise tier and intelligence addon
            await conn.execute(text("""
                INSERT INTO tenant_skus (
                    id, organization_id, tier, intelligence_addon, billing_cycle, 
                    is_active, current_period_start, current_period_end
                )
                VALUES (
                    gen_random_uuid(), :org_id, 'enterprise', 'advanced', 'MONTHLY',
                    true, CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days'
                )
            """), {"org_id": org_id})
            print('Created new enterprise SKU with advanced intelligence addon')
        
        # Verify
        result = await conn.execute(text("""
            SELECT tier, intelligence_addon, is_active FROM tenant_skus WHERE organization_id = :org_id
        """), {"org_id": org_id})
        final = result.fetchone()
        print(f'Final SKU: tier={final[0]}, intelligence_addon={final[1]}, is_active={final[2]}')


if __name__ == "__main__":
    asyncio.run(create_or_update_sku())
