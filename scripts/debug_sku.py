"""Debug SKU enforcement to find the issue."""
import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def debug_sku():
    async with async_session_maker() as db:
        # Check tenant_skus table data
        print('=== TENANT_SKUS DATA ===')
        result = await db.execute(text('''
            SELECT organization_id, tier, intelligence_addon, is_active, feature_overrides 
            FROM tenant_skus 
            LIMIT 10
        '''))
        rows = result.fetchall()
        for row in rows:
            print(f'  org_id: {row[0]}')
            print(f'    tier: {row[1]} (type: {type(row[1])})')
            print(f'    intel: {row[2]} (type: {type(row[2])})')
            print(f'    active: {row[3]}')
            print(f'    overrides: {row[4]}')
            print()
        
        # Check the postgres enum values
        print('=== POSTGRES ENUM VALUES ===')
        result = await db.execute(text("SELECT unnest(enum_range(NULL::skutier))"))
        rows = result.fetchall()
        print(f'skutier enum values: {[r[0] for r in rows]}')
        
        result = await db.execute(text("SELECT unnest(enum_range(NULL::intelligenceaddon))"))
        rows = result.fetchall()
        print(f'intelligenceaddon enum values: {[r[0] for r in rows]}')
        
        # Check Python enum values
        print('\n=== PYTHON ENUM VALUES ===')
        from app.models.sku_enums import SKUTier, IntelligenceAddon
        print(f'Python SKUTier values: {[e.value for e in SKUTier]}')
        print(f'Python IntelligenceAddon values: {[e.value for e in IntelligenceAddon]}')
        
        # Check the TIER_FEATURES mapping
        print('\n=== TIER_FEATURES MAPPING ===')
        from app.services.feature_flags import TIER_FEATURES
        for tier, features in TIER_FEATURES.items():
            print(f'  {tier} ({tier.value}): {len(features)} features')
        
        # Now test the actual feature check logic
        print('\n=== TESTING FEATURE CHECK LOGIC ===')
        from app.services.feature_flags import FeatureFlagService
        from app.models.sku import Feature
        
        # Pick an org with Core tier to test
        result = await db.execute(text('''
            SELECT ts.organization_id, ts.tier, ts.intelligence_addon, o.name
            FROM tenant_skus ts
            JOIN organizations o ON o.id = ts.organization_id
            WHERE ts.is_active = true
        '''))
        rows = result.fetchall()
        
        service = FeatureFlagService(db)
        
        for row in rows:
            org_id, tier, intel, name = row
            print(f'\nOrg: {name}')
            print(f'  Tier from DB: {tier} (type: {type(tier)})')
            print(f'  Intel from DB: {intel} (type: {type(intel)})')
            
            # Get enabled features
            enabled = await service.get_enabled_features(org_id)
            print(f'  Enabled features count: {len(enabled)}')
            
            # Check specific features
            test_features = [
                Feature.GL_ENABLED,  # CORE
                Feature.PAYROLL,     # PROFESSIONAL
                Feature.WORM_VAULT,  # ENTERPRISE
                Feature.BENFORDS_LAW, # INTELLIGENCE
            ]
            for f in test_features:
                has = await service.has_feature(org_id, f)
                print(f'    {f.value}: {has}')

if __name__ == '__main__':
    asyncio.run(debug_sku())
