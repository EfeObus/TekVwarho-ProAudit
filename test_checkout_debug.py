"""Debug script to test checkout endpoint"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_checkout():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app.services.billing_service import BillingService, PaystackProvider
    from app.models.sku import SKUTier, IntelligenceAddon
    from app.services.billing_service import BillingCycle
    from uuid import uuid4
    
    # Test with mock org
    engine = create_async_engine(settings.database_url_async)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        service = BillingService(db)
        
        try:
            intent = await service.create_payment_intent(
                organization_id=uuid4(),  # Fake org for testing
                tier=SKUTier.PROFESSIONAL,
                billing_cycle=BillingCycle.MONTHLY,
                admin_email='test@example.com',
                intelligence_addon=None,
                additional_users=0,
                callback_url='http://localhost:5120/billing/callback',
            )
            print('SUCCESS:', intent)
        except Exception as e:
            print(f'ERROR TYPE: {type(e).__name__}')
            print(f'ERROR: {e}')
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_checkout())
